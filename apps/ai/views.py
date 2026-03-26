"""
AI API Views for CampusHub
Provides REST endpoints for AI services
"""

from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ai.services import (
    SemanticSearchService,
    RecommendationService,
    ChatbotService,
    SummarizationService,
    StudyGoalService,
    SearchType,
    ChatResponse,
)
from apps.ai.models import StudyGoal, StudyGoalMilestone, GoalReminder
from apps.payments.freemium import Feature, can_access_feature


def _feature_access_denied(user, feature: Feature):
    has_access, reason = can_access_feature(user, feature)
    if has_access:
        return None
    return Response(
        {
            "error": "Feature not available",
            "reason": reason,
            "feature": feature.value,
            "upgrade_url": "/settings/billing/upgrade/",
        },
        status=status.HTTP_403_FORBIDDEN,
    )


class AISearchView(APIView):
    """
    AI-powered semantic search endpoint.
    
    Supports keyword, semantic, and hybrid search.
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="AI Semantic Search",
        description="Search resources using AI-powered semantic search",
        parameters=[
            OpenApiParameter(name='q', description='Search query', required=True, type=str),
            OpenApiParameter(name='type', description='Search type: keyword, semantic, hybrid', 
                          type=str, default='hybrid'),
            OpenApiParameter(name='resource_type', description='Filter by resource type', type=str),
            OpenApiParameter(name='faculty_id', description='Filter by faculty ID', type=str),
            OpenApiParameter(name='department_id', description='Filter by department ID', type=str),
            OpenApiParameter(name='course_id', description='Filter by course ID', type=str),
            OpenApiParameter(name='unit_id', description='Filter by unit ID', type=str),
            OpenApiParameter(name='year_of_study', description='Filter by year of study', type=int),
            OpenApiParameter(name='limit', description='Number of results', type=int, default=10),
        ]
    )
    def get(self, request, *args, **kwargs):
        denied_response = _feature_access_denied(request.user, Feature.AI_FEATURES)
        if denied_response:
            return denied_response

        query = request.query_params.get('q', '')
        search_type = request.query_params.get('type', 'hybrid')
        limit = int(request.query_params.get('limit', 10))
        
        if not query:
            return Response(
                {'error': 'Query parameter "q" is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Parse search type
        try:
            search_type_enum = SearchType(search_type.lower())
        except ValueError:
            search_type_enum = SearchType.HYBRID
        
        # Build filters
        filters = {}
        for param in ['resource_type', 'faculty_id', 'department_id', 'course_id', 'unit_id']:
            value = request.query_params.get(param)
            if value:
                filters[param] = value
        
        year = request.query_params.get('year_of_study')
        if year:
            try:
                filters['year_of_study'] = int(year)
            except ValueError:
                pass
        
        # Perform search
        results = SemanticSearchService.search_resources(
            query=query,
            search_type=search_type_enum,
            filters=filters if filters else None,
            top_k=limit
        )
        
        # Serialize results
        data = [
            {
                'id': r.id,
                'title': r.title,
                'description': r.description,
                'type': r.type,
                'score': round(r.score, 3),
                'metadata': r.metadata
            }
            for r in results
        ]
        
        return Response({
            'query': query,
            'search_type': search_type_enum.value,
            'count': len(data),
            'results': data
        })


class AIRecommendationsView(APIView):
    """
    Get personalized AI recommendations.
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="AI Recommendations",
        description="Get personalized resource recommendations",
        parameters=[
            OpenApiParameter(name='limit', description='Number of recommendations', 
                          type=int, default=10),
            OpenApiParameter(name='include_popular', description='Include popular items',
                          type=bool, default=True),
        ]
    )
    def get(self, request, *args, **kwargs):
        denied_response = _feature_access_denied(request.user, Feature.AI_FEATURES)
        if denied_response:
            return denied_response

        limit = int(request.query_params.get('limit', 10))
        include_popular = request.query_params.get('include_popular', 'true').lower() == 'true'
        
        recommendations = RecommendationService.get_user_recommendations(
            user=request.user,
            limit=limit,
            include_popular=include_popular
        )
        
        data = [
            {
                'id': r.id,
                'title': r.title,
                'description': r.description,
                'type': r.type,
                'score': round(r.score, 3),
                'reason': r.reason,
                'metadata': r.metadata
            }
            for r in recommendations
        ]
        
        return Response({
            'user': str(request.user.id),
            'count': len(data),
            'recommendations': data
        })


class LearningPathView(APIView):
    """
    Get personalized learning path.
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Learning Path",
        description="Get personalized learning path based on user's course"
    )
    def get(self, request, *args, **kwargs):
        denied_response = _feature_access_denied(request.user, Feature.AI_FEATURES)
        if denied_response:
            return denied_response

        course_id = request.query_params.get('course_id')
        
        learning_path = RecommendationService.get_learning_path(
            user=request.user,
            course_id=course_id
        )
        
        return Response(learning_path)


class AIChatbotView(APIView):
    """
    AI Chatbot endpoint for student assistance.
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Chat with AI Assistant",
        description="Get AI-powered assistance for platform questions",
        request={
            'application/json': {
                'properties': {
                    'message': {'type': 'string', 'description': 'User message'},
                    'clear_context': {'type': 'boolean', 'description': 'Clear conversation context'}
                },
                'required': ['message']
            }
        }
    )
    def post(self, request, *args, **kwargs):
        denied_response = _feature_access_denied(request.user, Feature.AI_CHAT)
        if denied_response:
            return denied_response

        message = request.data.get('message', '')
        clear_context = request.data.get('clear_context', False)
        
        if not message:
            return Response(
                {'error': 'Message is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user_id = str(request.user.id)
        
        # Clear context if requested
        if clear_context:
            ChatbotService.clear_context(user_id)
        
        # Process message
        response = ChatbotService.process_message(user_id, message, user=request.user)
        
        return Response({
            'message': response.message,
            'sources': response.sources,
            'suggested_actions': response.suggested_actions,
            'metadata': response.metadata
        })


class AISummarizationView(APIView):
    """
    AI Document Summarization endpoint.
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Summarize Text",
        description="Generate AI summary of text or document",
        request={
            'application/json': {
                'properties': {
                    'text': {'type': 'string', 'description': 'Text to summarize'},
                    'resource_id': {'type': 'string', 'description': 'Resource ID to summarize'},
                    'max_length': {'type': 'integer', 'description': 'Max summary length'},
                    'summary_type': {'type': 'string', 'description': 'brief, detailed, or auto'}
                }
            }
        }
    )
    def post(self, request, *args, **kwargs):
        denied_response = _feature_access_denied(request.user, Feature.AI_SUMMARIZATION)
        if denied_response:
            return denied_response

        text = request.data.get('text', '')
        resource_id = request.data.get('resource_id')
        max_length = int(request.data.get('max_length', 200))
        summary_type = request.data.get('summary_type', 'auto')
        
        if not text and not resource_id:
            return Response(
                {'error': 'Either text or resource_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get text to summarize
        if resource_id:
            result = SummarizationService.summarize_resource(resource_id)
        else:
            result = SummarizationService.summarize_text(
                text=text,
                max_length=max_length,
                summary_type=summary_type
            )
        
        return Response({
            'summary': result.summary,
            'key_points': result.key_points,
            'word_count': result.word_count,
            'reading_time_minutes': result.reading_time_minutes,
            'language': result.language
        })


# Convenience function for mobile/API consumers
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def public_chatbot(request):
    """
    Public chatbot endpoint (rate limited).
    """
    message = request.data.get('message', '')
    user_id = request.data.get('user_id', 'anonymous')
    
    if not message:
        return Response(
            {'error': 'Message is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    response = ChatbotService.process_message(user_id, message)
    
    return Response({
        'message': response.message,
        'suggested_actions': response.suggested_actions
    })


class StudyGoalGenerateView(APIView):
    """
    Generate AI-powered personalized study goals.
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Generate Study Goals",
        description="Generate personalized AI study goals based on performance and analytics",
        request={
            'application/json': {
                'properties': {
                    'goal_type': {
                        'type': 'string',
                        'description': 'Type of goals: short_term, medium_term, long_term, subject_specific, all',
                        'default': 'all'
                    },
                    'save': {
                        'type': 'boolean',
                        'description': 'Whether to save the generated goals',
                        'default': True
                    }
                }
            }
        }
    )
    def post(self, request, *args, **kwargs):
        denied_response = _feature_access_denied(request.user, Feature.AI_FEATURES)
        if denied_response:
            return denied_response

        goal_type = request.data.get('goal_type', 'all')
        save_goals = request.data.get('save', True)
        
        # Validate goal_type
        valid_types = ['short_term', 'medium_term', 'long_term', 'subject_specific', 'all']
        if goal_type not in valid_types:
            return Response(
                {'error': f'Invalid goal_type. Must be one of: {valid_types}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate goals
        generated_goals = StudyGoalService.generate_study_goals(
            user=request.user,
            goal_type=goal_type
        )
        
        # Convert to dict for response
        goals_data = []
        for goal in generated_goals:
            goals_data.append({
                'title': goal.title,
                'description': goal.description,
                'goal_type': goal.goal_type,
                'priority': goal.priority,
                'target_hours': goal.target_hours,
                'target_topics': goal.target_topics,
                'weak_areas': goal.weak_areas,
                'recommendations': goal.recommendations,
                'start_date': goal.start_date.isoformat() if goal.start_date else None,
                'target_date': goal.target_date.isoformat() if goal.target_date else None,
                'milestones': goal.milestones,
            })
        
        # Save if requested
        saved = []
        if save_goals:
            saved_goals = StudyGoalService.save_generated_goals(request.user, generated_goals)
            saved = [str(g.id) for g in saved_goals]
        
        return Response({
            'generated_count': len(goals_data),
            'goals': goals_data,
            'saved_goal_ids': saved,
        })


class StudyGoalListView(APIView):
    """
    Get user's study goals.
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        operation_id="api_ai_study_goals_list",
        summary="Get Study Goals",
        description="Get all study goals for the current user",
        parameters=[
            OpenApiParameter(name='status', description='Filter by status: active, completed, cancelled', type=str),
            OpenApiParameter(name='goal_type', description='Filter by goal type', type=str),
        ]
    )
    def get(self, request, *args, **kwargs):
        denied_response = _feature_access_denied(request.user, Feature.AI_FEATURES)
        if denied_response:
            return denied_response

        # Build filters
        filters = {'user': request.user}
        
        status = request.query_params.get('status')
        if status:
            filters['status'] = status
        
        goal_type = request.query_params.get('goal_type')
        if goal_type:
            filters['goal_type'] = goal_type
        
        # Get goals
        goals = StudyGoal.objects.filter(**filters).order_by('-created_at')
        
        # Serialize
        data = []
        for goal in goals:
            data.append({
                'id': str(goal.id),
                'title': goal.title,
                'description': goal.description,
                'goal_type': goal.goal_type,
                'status': goal.status,
                'priority': goal.priority,
                'target_hours': goal.target_hours,
                'target_topics': goal.target_topics,
                'progress': goal.progress,
                'completed_hours': goal.completed_hours,
                'weak_areas': goal.weak_areas,
                'ai_recommendations': goal.ai_recommendations,
                'start_date': goal.start_date.isoformat() if goal.start_date else None,
                'target_date': goal.target_date.isoformat() if goal.target_date else None,
                'completed_at': goal.completed_at.isoformat() if goal.completed_at else None,
                'created_at': goal.created_at.isoformat(),
                'milestones': [
                    {
                        'id': str(m.id),
                        'title': m.title,
                        'milestone_type': m.milestone_type,
                        'due_date': m.due_date.isoformat() if m.due_date else None,
                        'is_completed': m.is_completed,
                        'progress': m.progress,
                    }
                    for m in goal.milestones.all()
                ],
            })
        
        return Response({
            'count': len(data),
            'goals': data,
        })


class StudyGoalDetailView(APIView):
    """
    Get, update, or delete a specific study goal.
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        operation_id="api_ai_study_goals_retrieve",
        summary="Get Study Goal",
        description="Get details of a specific study goal"
    )
    def get(self, request, goal_id):
        denied_response = _feature_access_denied(request.user, Feature.AI_FEATURES)
        if denied_response:
            return denied_response

        try:
            goal = StudyGoal.objects.get(id=goal_id, user=request.user)
        except StudyGoal.DoesNotExist:
            return Response(
                {'error': 'Study goal not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response({
            'id': str(goal.id),
            'title': goal.title,
            'description': goal.description,
            'goal_type': goal.goal_type,
            'status': goal.status,
            'priority': goal.priority,
            'target_hours': goal.target_hours,
            'target_topics': goal.target_topics,
            'progress': goal.progress,
            'completed_hours': goal.completed_hours,
            'completed_topics': goal.completed_topics,
            'weak_areas': goal.weak_areas,
            'ai_recommendations': goal.ai_recommendations,
            'start_date': goal.start_date.isoformat() if goal.start_date else None,
            'target_date': goal.target_date.isoformat() if goal.target_date else None,
            'completed_at': goal.completed_at.isoformat() if goal.completed_at else None,
            'created_at': goal.created_at.isoformat(),
            'milestones': [
                {
                    'id': str(m.id),
                    'title': m.title,
                    'description': m.description,
                    'milestone_type': m.milestone_type,
                    'due_date': m.due_date.isoformat() if m.due_date else None,
                    'is_completed': m.is_completed,
                    'progress': m.progress,
                }
                for m in goal.milestones.all()
            ],
            'adjustments': StudyGoalService.get_goal_adjustments(goal),
        })
    
    @extend_schema(
        summary="Update Study Goal",
        description="Update progress and details of a study goal",
        request={
            'application/json': {
                'properties': {
                    'title': {'type': 'string'},
                    'description': {'type': 'string'},
                    'priority': {'type': 'string', 'enum': ['low', 'medium', 'high', 'urgent']},
                    'target_hours': {'type': 'number'},
                    'target_topics': {'type': 'array', 'items': {'type': 'string'}},
                    'progress': {'type': 'integer', 'minimum': 0, 'maximum': 100},
                    'completed_hours': {'type': 'number'},
                    'completed_topics': {'type': 'array', 'items': {'type': 'string'}},
                    'status': {'type': 'string', 'enum': ['active', 'completed', 'cancelled', 'expired']},
                }
            }
        }
    )
    def patch(self, request, goal_id):
        denied_response = _feature_access_denied(request.user, Feature.AI_FEATURES)
        if denied_response:
            return denied_response

        try:
            goal = StudyGoal.objects.get(id=goal_id, user=request.user)
        except StudyGoal.DoesNotExist:
            return Response(
                {'error': 'Study goal not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Update fields
        updatable_fields = [
            'title', 'description', 'priority', 'target_hours',
            'target_topics', 'progress', 'completed_hours', 'completed_topics', 'status'
        ]
        
        for field in updatable_fields:
            if field in request.data:
                setattr(goal, field, request.data[field])
        
        goal.save()
        
        return Response({
            'id': str(goal.id),
            'title': goal.title,
            'status': goal.status,
            'progress': goal.progress,
            'message': 'Study goal updated successfully',
        })
    
    @extend_schema(
        summary="Delete Study Goal",
        description="Delete a study goal"
    )
    def delete(self, request, goal_id):
        denied_response = _feature_access_denied(request.user, Feature.AI_FEATURES)
        if denied_response:
            return denied_response

        try:
            goal = StudyGoal.objects.get(id=goal_id, user=request.user)
        except StudyGoal.DoesNotExist:
            return Response(
                {'error': 'Study goal not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        goal.delete()
        
        return Response(
            {'message': 'Study goal deleted successfully'},
            status=status.HTTP_204_NO_CONTENT
        )


class StudyGoalCompleteView(APIView):
    """
    Mark a study goal as complete.
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Mark Goal Complete",
        description="Mark a study goal as completed",
        request={
            'application/json': {
                'properties': {
                    'completed_hours': {'type': 'number', 'description': 'Total hours studied'},
                    'completed_topics': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Topics completed'},
                }
            }
        }
    )
    def post(self, request, goal_id):
        denied_response = _feature_access_denied(request.user, Feature.AI_FEATURES)
        if denied_response:
            return denied_response

        try:
            goal = StudyGoal.objects.get(id=goal_id, user=request.user)
        except StudyGoal.DoesNotExist:
            return Response(
                {'error': 'Study goal not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Update completion data
        completed_hours = request.data.get('completed_hours')
        completed_topics = request.data.get('completed_topics', [])
        
        if completed_hours:
            goal.completed_hours = completed_hours
        
        if completed_topics:
            goal.completed_topics = completed_topics
        
        # Mark as complete
        goal.mark_complete()
        
        return Response({
            'id': str(goal.id),
            'title': goal.title,
            'status': goal.status,
            'progress': goal.progress,
            'completed_at': goal.completed_at.isoformat() if goal.completed_at else None,
            'message': 'Goal marked as completed!',
        })


class StudyGoalProgressView(APIView):
    """
    Update progress on a study goal.
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Update Progress",
        description="Update progress on a study goal",
        request={
            'application/json': {
                'properties': {
                    'hours': {'type': 'number', 'description': 'Hours studied'},
                    'topic': {'type': 'string', 'description': 'Topic completed'},
                },
                'required': ['hours']
            }
        }
    )
    def post(self, request, goal_id):
        denied_response = _feature_access_denied(request.user, Feature.AI_FEATURES)
        if denied_response:
            return denied_response

        try:
            goal = StudyGoal.objects.get(id=goal_id, user=request.user)
        except StudyGoal.DoesNotExist:
            return Response(
                {'error': 'Study goal not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        hours = request.data.get('hours', 0)
        topic = request.data.get('topic')
        
        if hours <= 0 and not topic:
            return Response(
                {'error': 'Either hours or topic is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update progress
        goal.update_progress(hours=hours, topic=topic)
        
        return Response({
            'id': str(goal.id),
            'title': goal.title,
            'progress': goal.progress,
            'completed_hours': goal.completed_hours,
            'completed_topics': goal.completed_topics,
            'message': 'Progress updated successfully',
        })
