"""
AI Services for CampusHub
Provides semantic search, recommendations, chatbot, and summarization
"""

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from urllib import error as urlerror, request as urlrequest

import numpy as np
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class SearchType(Enum):
    """Types of search available."""
    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


@dataclass
class SearchResult:
    """Result from semantic search."""
    id: str
    title: str
    description: str
    type: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Recommendation:
    """A recommended item."""
    id: str
    title: str
    description: str
    type: str
    score: float
    reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatMessage:
    """A chat message."""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ChatResponse:
    """Response from chatbot."""
    message: str
    sources: List[Dict[str, Any]] = field(default_factory=list)
    suggested_actions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SummaryResult:
    """Document summary result."""
    summary: str
    key_points: List[str]
    word_count: int
    reading_time_minutes: float
    language: str


class SemanticSearchService:
    """
    Semantic search service using embeddings.
    
    For production, this would use:
    - OpenAI Embeddings (text-embedding-3-small)
    - Pinecone/Weaviate/Chroma for vector storage
    - Sentence Transformers for local embeddings
    
    This implementation provides a working foundation with:
    - TF-IDF based similarity for keyword matching
    - Mock embeddings for demonstration
    - Hybrid search combining both approaches
    """

    # Stopwords to ignore in search
    STOPWORDS = {
        'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
        'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from', 'as',
        'into', 'through', 'during', 'before', 'after', 'above', 'below',
        'between', 'under', 'again', 'further', 'then', 'once', 'here',
        'there', 'when', 'where', 'why', 'how', 'all', 'each', 'few',
        'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only',
        'own', 'same', 'so', 'than', 'too', 'very', 'just', 'and', 'but',
        'if', 'or', 'because', 'until', 'while', 'this', 'that', 'these',
        'those', 'what', 'which', 'who', 'whom', 'its', 'also'
    }

    @classmethod
    def get_embedding(cls, text: str) -> List[float]:
        """
        Get embedding vector for text.
        
        In production, replace with actual embedding API call:
        - OpenAI: client.embeddings.create()
        - HuggingFace: sentence_transformers model
        """
        # Generate a deterministic embedding based on text hash
        # This is a simplified version for demonstration
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        
        # Create a 384-dimensional vector from the hash
        vector = []
        for i in range(0, len(text_hash), 8):
            chunk = text_hash[i:i+8]
            value = int(chunk, 16) / (16 ** 8)
            vector.append(value * 2 - 1)  # Normalize to [-1, 1]
        
        # Pad or truncate to 384 dimensions
        while len(vector) < 384:
            vector.extend(vector[:min(len(vector), 384 - len(vector))])
        return vector[:384]

    @classmethod
    def cosine_similarity(cls, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)

    @classmethod
    def compute_tfidf(cls, documents: List[str]) -> Dict[str, List[Tuple[str, float]]]:
        """
        Compute TF-IDF vectors for documents.
        Returns dict of {doc_id: [(word, tfidf_score)]}
        """
        # Tokenize documents
        tokenized = []
        for doc in documents:
            words = re.findall(r'\b\w+\b', doc.lower())
            words = [w for w in words if w not in cls.STOPWORDS and len(w) > 2]
            tokenized.append(words)
        
        # Compute document frequency
        doc_count = len(documents)
        df = {}
        for tokens in tokenized:
            for word in set(tokens):
                df[word] = df.get(word, 0) + 1
        
        # Compute TF-IDF for each document
        tfidf_vectors = {}
        for i, tokens in enumerate(tokenized):
            tf = {}
            for token in tokens:
                tf[token] = tf.get(token, 0) + 1
            
            # Normalize by document length
            doc_length = len(tokens) if tokens else 1
            
            tfidf = []
            for word, count in tf.items():
                tf_score = count / doc_length
                idf = np.log(doc_count / (df.get(word, 1) + 1)) + 1
                tfidf.append((word, tf_score * idf))
            
            tfidf_vectors[i] = sorted(tfidf, key=lambda x: x[1], reverse=True)[:50]
        
        return tfidf_vectors

    @classmethod
    def keyword_search(cls, query: str, documents: List[Dict]) -> List[SearchResult]:
        """Perform keyword-based search."""
        query_tokens = set(re.findall(r'\b\w+\b', query.lower()))
        query_tokens = query_tokens - cls.STOPWORDS
        
        results = []
        for doc in documents:
            doc_text = f"{doc.get('title', '')} {doc.get('description', '')} {doc.get('content', '')}".lower()
            doc_tokens = set(re.findall(r'\b\w+\b', doc_text))
            
            # Calculate Jaccard similarity
            intersection = len(query_tokens & doc_tokens)
            union = len(query_tokens | doc_tokens)
            score = intersection / union if union > 0 else 0
            
            if score > 0:
                results.append(SearchResult(
                    id=str(doc.get('id', '')),
                    title=doc.get('title', ''),
                    description=doc.get('description', ''),
                    type=doc.get('type', 'resource'),
                    score=score,
                    metadata=doc.get('metadata', {})
                ))
        
        return sorted(results, key=lambda x: x.score, reverse=True)

    @classmethod
    def semantic_search(
        cls,
        query: str,
        documents: List[Dict],
        top_k: int = 10
    ) -> List[SearchResult]:
        """Perform semantic search using embeddings."""
        if not documents:
            return []
        
        # Get query embedding
        query_embedding = cls.get_embedding(query)
        
        # Get document embeddings and compute similarities
        results = []
        for doc in documents:
            doc_text = f"{doc.get('title', '')} {doc.get('description', '')}"
            doc_embedding = cls.get_embedding(doc_text)
            
            similarity = cls.cosine_similarity(query_embedding, doc_embedding)
            
            results.append(SearchResult(
                id=str(doc.get('id', '')),
                title=doc.get('title', ''),
                description=doc.get('description', ''),
                type=doc.get('type', 'resource'),
                score=float(similarity),
                metadata=doc.get('metadata', {})
            ))
        
        return sorted(results, key=lambda x: x.score, reverse=True)[:top_k]

    @classmethod
    def hybrid_search(
        cls,
        query: str,
        documents: List[Dict],
        semantic_weight: float = 0.6,
        keyword_weight: float = 0.4,
        top_k: int = 10
    ) -> List[SearchResult]:
        """Combine semantic and keyword search results."""
        semantic_results = {r.id: r for r in cls.semantic_search(query, documents, top_k)}
        keyword_results = {r.id: r for r in cls.keyword_search(query, documents)}
        
        # Normalize scores
        max_semantic = max((r.score for r in semantic_results.values()), default=1)
        max_keyword = max((r.score for r in keyword_results.values()), default=1)
        
        # Combine scores
        combined = {}
        all_ids = set(semantic_results.keys()) | set(keyword_results.keys())
        
        for doc_id in all_ids:
            sem_score = semantic_results.get(doc_id, SearchResult(
                id=doc_id, title='', description='', type='', score=0
            )).score / max_semantic if doc_id in semantic_results else 0
            
            key_score = keyword_results.get(doc_id, SearchResult(
                id=doc_id, title='', description='', type='', score=0
            )).score / max_keyword if doc_id in keyword_results else 0
            
            final_score = (semantic_weight * sem_score) + (keyword_weight * key_score)
            
            if doc_id in semantic_results:
                result = semantic_results[doc_id]
                combined[doc_id] = SearchResult(
                    id=result.id,
                    title=result.title,
                    description=result.description,
                    type=result.type,
                    score=final_score,
                    metadata=result.metadata
                )
        
        return sorted(combined.values(), key=lambda x: x.score, reverse=True)[:top_k]

    @classmethod
    def search_resources(
        cls,
        query: str,
        search_type: SearchType = SearchType.HYBRID,
        filters: Optional[Dict] = None,
        top_k: int = 10
    ) -> List[SearchResult]:
        """
        Search resources with optional filters.
        
        Args:
            query: Search query string
            search_type: Type of search (keyword, semantic, hybrid)
            filters: Optional filters (type, category, year, etc.)
            top_k: Number of results to return
        """
        from apps.resources.models import Resource
        
        # Base queryset
        qs = Resource.objects.filter(status='approved')
        
        # Apply filters
        if filters:
            if filters.get('resource_type'):
                qs = qs.filter(resource_type=filters['resource_type'])
            if filters.get('faculty_id'):
                qs = qs.filter(faculty_id=filters['faculty_id'])
            if filters.get('department_id'):
                qs = qs.filter(department_id=filters['department_id'])
            if filters.get('course_id'):
                qs = qs.filter(course_id=filters['course_id'])
            if filters.get('unit_id'):
                qs = qs.filter(unit_id=filters['unit_id'])
            if filters.get('year_of_study'):
                qs = qs.filter(year_of_study=filters['year_of_study'])
        
        # Get documents
        documents = []
        for r in qs.select_related('course', 'unit', 'faculty', 'department'):
            documents.append({
                'id': str(r.id),
                'title': r.title,
                'description': r.description or '',
                'content': ' '.join(
                    filter(
                        None,
                        [
                            r.title,
                            r.description or '',
                            r.tags or '',
                            r.ai_summary or '',
                            (r.ocr_text or '')[:2000],
                            r.course.name if r.course else '',
                            r.unit.name if r.unit else '',
                        ],
                    )
                ),
                'type': 'resource',
                'metadata': {
                    'resource_type': r.resource_type,
                    'faculty': r.faculty.name if r.faculty else None,
                    'department': r.department.name if r.department else None,
                    'course': r.course.name if r.course else None,
                    'unit': r.unit.name if r.unit else None,
                    'course_id': str(r.course_id) if r.course_id else None,
                    'unit_id': str(r.unit_id) if r.unit_id else None,
                    'slug': r.slug,
                    'file_type': r.file_type,
                    'download_count': r.download_count,
                    'rating': r.average_rating,
                }
            })
        
        # Perform search
        if search_type == SearchType.KEYWORD:
            return cls.keyword_search(query, documents)[:top_k]
        elif search_type == SearchType.SEMANTIC:
            return cls.semantic_search(query, documents, top_k)
        else:
            return cls.hybrid_search(query, documents, top_k=top_k)


class RecommendationService:
    """
    Smart recommendation service for personalized learning paths.
    
    Uses collaborative filtering and content-based approaches:
    - User behavior analysis
    - Content similarity
    - Learning path progression
    - Trending/popular items
    """

    @staticmethod
    def _get_user_learning_context(user) -> Dict[str, Any]:
        """Resolve learning context from the real User model with profile fallback."""
        user_profile = getattr(user, "profile", None)
        return {
            "course": getattr(user, "course", None) or getattr(user_profile, "course", None),
            "faculty": getattr(user, "faculty", None) or getattr(user_profile, "faculty", None),
            "year_of_study": getattr(user, "year_of_study", None)
            or getattr(user_profile, "year_of_study", None),
        }

    @classmethod
    def get_user_recommendations(
        cls,
        user,
        limit: int = 10,
        include_popular: bool = True
    ) -> List[Recommendation]:
        """
        Get personalized recommendations for a user.
        
        Factors considered:
        1. User's course and enrolled units
        2. Download history
        3. Search history
        4. Favorites and bookmarks
        5. Similar users' behavior
        """
        from apps.resources.models import Resource
        
        recommendations = []
        user_context = cls._get_user_learning_context(user)
        user_course = user_context["course"]
        user_faculty = user_context["faculty"]
        user_year = user_context["year_of_study"]
        
        # 1. Course-related resources
        if user_course:
            course_resources = Resource.objects.filter(
                course=user_course,
                status='approved'
            ).order_by('-download_count')[:5]
            
            for r in course_resources:
                recommendations.append(Recommendation(
                    id=str(r.id),
                    title=r.title,
                    description=r.description or '',
                    type='course',
                    score=0.9,
                    reason=f"Related to your course: {user_course.name}",
                    metadata={'resource_type': r.resource_type}
                ))
        
        # 2. Faculty resources
        if user_faculty:
            faculty_resources = Resource.objects.filter(
                faculty=user_faculty,
                status='approved'
            ).exclude(
                id__in=[r.id for r in recommendations]
            ).order_by('-average_rating')[:5]
            
            for r in faculty_resources:
                recommendations.append(Recommendation(
                    id=str(r.id),
                    title=r.title,
                    description=r.description or '',
                    type='faculty',
                    score=0.8,
                    reason=f"Popular in {user_faculty.name}",
                    metadata={'resource_type': r.resource_type}
                ))
        
        # 3. Year-specific resources
        if user_year:
            year_resources = Resource.objects.filter(
                year_of_study=user_year,
                status='approved'
            ).exclude(
                id__in=[r.id for r in recommendations]
            ).order_by('-created_at')[:3]
            
            for r in year_resources:
                recommendations.append(Recommendation(
                    id=str(r.id),
                    title=r.title,
                    description=r.description or '',
                    type='year',
                    score=0.7,
                    reason=f"Relevant for Year {user_year}",
                    metadata={'resource_type': r.resource_type}
                ))
        
        # 4. Trending/Popular (if enabled)
        if include_popular:
            trending = Resource.objects.filter(
                status='approved'
            ).exclude(
                id__in=[r.id for r in recommendations]
            ).order_by('-download_count', '-view_count')[:5]
            
            for r in trending:
                recommendations.append(Recommendation(
                    id=str(r.id),
                    title=r.title,
                    description=r.description or '',
                    type='trending',
                    score=0.6,
                    reason="Trending on CampusHub",
                    metadata={'resource_type': r.resource_type, 'download_count': r.download_count}
                ))
        
        # Sort by score and limit
        recommendations.sort(key=lambda x: x.score, reverse=True)
        return recommendations[:limit]

    @classmethod
    def get_learning_path(cls, user, course_id: str = None) -> Dict:
        """
        Generate a personalized learning path.
        
        Returns a structured learning path with:
        - Recommended resources in order
        - Estimated completion time
        - Prerequisites
        """
        from apps.resources.models import Resource
        from apps.courses.models import Course, Unit
        
        path = {
            'courses': [],
            'total_hours': 0,
            'resources_count': 0
        }
        
        # Get user's course or specified course
        if course_id:
            try:
                course = Course.objects.get(id=course_id)
            except Course.DoesNotExist:
                return path
        else:
            course = cls._get_user_learning_context(user)["course"]
        
        if not course:
            return path
        
        # Get units for the course
        units = Unit.objects.filter(course=course).order_by('semester', 'name')
        
        for unit in units:
            # Get resources for each unit
            resources = Resource.objects.filter(
                unit=unit,
                status='approved'
            ).order_by('-download_count')[:3]
            
            unit_data = {
                'unit_id': str(unit.id),
                'unit_name': unit.name,
                'unit_code': unit.code,
                'semester': unit.semester,
                'resources': [],
                'estimated_hours': len(resources) * 2  # 2 hours per resource estimate
            }
            
            for r in resources:
                unit_data['resources'].append({
                    'id': str(r.id),
                    'title': r.title,
                    'type': r.resource_type,
                    'duration_minutes': 30
                })
                path['resources_count'] += 1
            
            path['total_hours'] += unit_data['estimated_hours']
            path['courses'].append(unit_data)
        
        return path


class ChatbotService:
    """
    AI Chatbot service for student assistance.
    
    Provides:
    - General Q&A about the platform
    - Resource recommendations
    - Academic guidance
    - Study tips
    """

    # Knowledge base for common questions
    KNOWLEDGE_BASE = {
        'how_to_upload': {
            'keywords': ['upload', 'share', 'add', 'contribute'],
            'response': "To upload a resource:\n1. Go to 'Upload Resource' in the menu\n2. Choose your file (PDF, DOC, PPT, etc.)\n3. Fill in the title and description\n4. Select the course and unit\n5. Add relevant tags\n6. Click Upload\n\nYour resource will be reviewed by moderators before going live.",
            'actions': ['Go to Upload', 'View My Uploads']
        },
        'how_to_download': {
            'keywords': ['download', 'get', 'save', 'access'],
            'response': "To download a resource:\n1. Search for the resource or browse by course\n2. Click on the resource to view details\n3. Click the 'Download' button\n4. The file will be saved to your device\n\nYou can find all downloaded files in the 'Downloads' section.",
            'actions': ['Browse Resources', 'View Downloads']
        },
        'how_to_verify': {
            'keywords': ['verify', 'email', 'confirm', 'activation'],
            'response': "To verify your email:\n1. Check your inbox for the verification email\n2. Click the verification link\n3. If you didn't receive it, go to Settings > Verify Email\n\nVerified accounts get access to all features!",
            'actions': ['Resend Verification']
        },
        'forgot_password': {
            'keywords': ['password', 'forgot', 'reset', 'change'],
            'response': "To reset your password:\n1. Go to Login page\n2. Click 'Forgot Password'\n3. Enter your email\n4. Check your inbox for reset link\n5. Create a new password",
            'actions': ['Reset Password']
        },
        'storage_info': {
            'keywords': ['storage', 'space', 'limit', 'upgrade'],
            'response': "Your storage quota depends on your plan:\n- Free: 1GB\n- Premium: 50GB\n- Pro: Unlimited\n\nYou can upgrade in Settings > Storage > Upgrade Plan",
            'actions': ['View Storage', 'Upgrade Plan']
        },
        'study_groups': {
            'keywords': ['study group', 'collaborate', 'team', 'group'],
            'response': "Study Groups let you collaborate with peers:\n1. Go to Study Groups\n2. Create a new group or join existing\n3. Share resources within the group\n4. Chat with members\n5. Schedule study sessions",
            'actions': ['View Study Groups', 'Create Group']
        },
        'moderation': {
            'keywords': ['pending', 'review', 'approve', 'reject', 'moderation'],
            'response': "Resource moderation ensures quality:\n- Uploaded resources are reviewed by moderators\n- This usually takes 24-48 hours\n- You'll be notified when your resource is approved/rejected\n- Check 'My Uploads' for status",
            'actions': ['View My Uploads']
        }
    }

    # Context for conversation
    conversation_context: Dict[str, List[ChatMessage]] = {}
    MAX_CONTEXT_MESSAGES = 12
    MAX_HISTORY_FOR_LLM = 6
    MAX_SOURCE_COUNT = 4
    OPENAI_CHAT_COMPLETIONS_URL = 'https://api.openai.com/v1/chat/completions'

    INTENT_KEYWORDS = {
        'resource_search': [
            'find', 'search', 'look for', 'show me', 'need notes', 'resource',
            'resources', 'notes', 'past paper', 'past papers', 'slides', 'book',
            'books', 'pdf', 'tutorial', 'materials', 'document',
        ],
        'recommendations': [
            'recommend', 'suggest', 'what should i study', 'what next',
            'personalized', 'for me', 'help me choose',
        ],
        'learning_path': [
            'learning path', 'study plan', 'roadmap', 'revision plan',
            'syllabus plan', 'plan my studies',
        ],
        'summary': [
            'summarize', 'summary', 'tl;dr', 'key points', 'brief this',
            'explain this file', 'condense',
        ],
        'greeting': [
            'hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening',
        ],
    }
    INTENT_PRIORITY = {
        'summary': 5,
        'learning_path': 4,
        'recommendations': 3,
        'resource_search': 2,
        'greeting': 1,
    }

    @classmethod
    def _keyword_in_message(cls, message: str, keyword: str) -> bool:
        """Match a keyword or phrase without accidental partial-word hits."""
        normalized_keyword = keyword.strip().lower()
        if not normalized_keyword:
            return False
        if ' ' in normalized_keyword:
            return normalized_keyword in message
        return bool(re.search(rf'\b{re.escape(normalized_keyword)}\b', message))

    @classmethod
    def _normalize_message(cls, message: str) -> str:
        """Normalize user input for intent matching."""
        return re.sub(r'\s+', ' ', (message or '').strip()).lower()

    @classmethod
    def _trim_context(cls, user_id: str):
        """Keep only the recent conversation window in memory."""
        if len(cls.conversation_context.get(user_id, [])) > cls.MAX_CONTEXT_MESSAGES:
            cls.conversation_context[user_id] = cls.conversation_context[user_id][
                -cls.MAX_CONTEXT_MESSAGES:
            ]

    @classmethod
    def _match_knowledge_base(cls, message: str) -> Optional[Dict[str, Any]]:
        """Find the strongest knowledge-base match for a message."""
        query_tokens = set(re.findall(r'\b\w+\b', message))
        best_match: Optional[Dict[str, Any]] = None
        best_score = 0.0

        for key, data in cls.KNOWLEDGE_BASE.items():
            score = 0.0
            for keyword in data['keywords']:
                keyword_normalized = keyword.lower()
                keyword_tokens = set(re.findall(r'\b\w+\b', keyword_normalized))
                if cls._keyword_in_message(message, keyword_normalized):
                    score += max(1.0, len(keyword_tokens) * 2.0)
                else:
                    score += len(query_tokens & keyword_tokens) * 0.5

            if score > best_score:
                best_score = score
                best_match = {
                    'key': key,
                    'score': round(score, 2),
                    'data': data,
                }

        return best_match if best_match and best_score > 0 else None

    @classmethod
    def _detect_intent(
        cls,
        normalized_message: str,
        knowledge_match: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Classify the user request into a chat intent."""
        if not normalized_message:
            return 'general'

        question_phrases = ('how do', 'where do', 'can i', 'how can', 'what is')
        if knowledge_match and (
            normalized_message.endswith('?')
            or any(phrase in normalized_message for phrase in question_phrases)
        ):
            return 'platform_help'

        intent_scores = {}
        for intent, keywords in cls.INTENT_KEYWORDS.items():
            score = sum(
                1 for keyword in keywords if cls._keyword_in_message(normalized_message, keyword)
            )
            if score > 0:
                intent_scores[intent] = score

        if intent_scores:
            return max(
                intent_scores.items(),
                key=lambda item: (item[1], cls.INTENT_PRIORITY.get(item[0], 0)),
            )[0]

        if knowledge_match:
            return 'platform_help'

        if normalized_message.endswith('?') and any(
            phrase in normalized_message for phrase in ['how do', 'where do', 'can i']
        ):
            return 'platform_help'

        return 'general'

    @classmethod
    def _get_user_learning_context(cls, user) -> Dict[str, Any]:
        """Resolve a compact user-learning context for prompts and filtering."""
        if not user:
            return {}

        context = RecommendationService._get_user_learning_context(user)
        return {
            'name': user.get_full_name() or user.email.split('@')[0],
            'role': getattr(user, 'role', ''),
            'course': context.get('course'),
            'faculty': context.get('faculty'),
            'year_of_study': context.get('year_of_study'),
        }

    @classmethod
    def _build_resource_filters(cls, user) -> Dict[str, Any]:
        """Build user-aware search filters to bias results toward relevant resources."""
        context = cls._get_user_learning_context(user)
        filters: Dict[str, Any] = {}

        if context.get('faculty'):
            filters['faculty_id'] = str(context['faculty'].id)
        if context.get('course'):
            filters['course_id'] = str(context['course'].id)
        if context.get('year_of_study'):
            filters['year_of_study'] = context['year_of_study']

        return filters

    @classmethod
    def _get_resource_matches(
        cls,
        query: str,
        user=None,
        limit: int = 5,
    ) -> List[Tuple[SearchResult, Any]]:
        """Find resource matches with user-aware filters and a global fallback."""
        from apps.resources.models import Resource

        query = (query or '').strip()
        if not query:
            return []

        filters = cls._build_resource_filters(user)
        results = SemanticSearchService.search_resources(
            query=query,
            search_type=SearchType.KEYWORD,
            filters=filters or None,
            top_k=limit,
        )

        if not results:
            results = SemanticSearchService.search_resources(
                query=query,
                search_type=SearchType.KEYWORD,
                filters=None,
                top_k=limit,
            )

        if not results:
            fallback_results = SemanticSearchService.search_resources(
                query=query,
                search_type=SearchType.HYBRID,
                filters=filters or None,
                top_k=limit,
            )
            results = [item for item in fallback_results if item.score >= 0.2]

        if not results and filters:
            fallback_results = SemanticSearchService.search_resources(
                query=query,
                search_type=SearchType.HYBRID,
                filters=None,
                top_k=limit,
            )
            results = [item for item in fallback_results if item.score >= 0.2]

        resource_map = {
            str(resource.id): resource
            for resource in Resource.objects.select_related(
                'course',
                'unit',
                'faculty',
                'department',
            ).filter(id__in=[result.id for result in results])
        }

        enriched_results: List[Tuple[SearchResult, Any]] = []
        for result in results:
            resource = resource_map.get(result.id)
            if resource:
                enriched_results.append((result, resource))
        return enriched_results

    @classmethod
    def _resource_to_source(cls, result: SearchResult, resource) -> Dict[str, Any]:
        """Convert a matched resource into a mobile-friendly source payload."""
        subtitle_parts = [
            resource.resource_type.replace('_', ' ').title(),
            resource.course.name if resource.course else None,
            resource.unit.name if resource.unit else None,
        ]
        subtitle = ' • '.join([part for part in subtitle_parts if part])

        return {
            'id': str(resource.id),
            'title': resource.title,
            'subtitle': subtitle,
            'route': f"/(student)/resource/{resource.id}",
            'url': getattr(getattr(resource, 'file', None), 'url', None) if resource.file else None,
            'type': resource.resource_type,
            'score': round(result.score, 3),
        }

    @classmethod
    def _resource_context_text(
        cls,
        resource_matches: List[Tuple[SearchResult, Any]],
        max_chars: int = 2200,
    ) -> str:
        """Build concise retrieval context for the LLM or local fallback."""
        snippets: List[str] = []

        for _, resource in resource_matches[: cls.MAX_SOURCE_COUNT]:
            content_bits = [
                resource.description or '',
                resource.ai_summary or '',
                (resource.ocr_text or '')[:700],
            ]
            snippet = ' '.join([bit.strip() for bit in content_bits if bit and bit.strip()])
            snippets.append(
                f"Title: {resource.title}\n"
                f"Type: {resource.resource_type}\n"
                f"Course: {resource.course.name if resource.course else 'Unknown'}\n"
                f"Unit: {resource.unit.name if resource.unit else 'Unknown'}\n"
                f"Content: {snippet[:900]}"
            )

        combined = '\n\n'.join(snippets)
        return combined[:max_chars]

    @classmethod
    def _call_openai_chat(
        cls,
        message: str,
        user=None,
        history: Optional[List[ChatMessage]] = None,
        context_text: str = '',
        knowledge_match: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Call OpenAI chat completions if configured, otherwise return None."""
        api_key = getattr(settings, 'OPENAI_API_KEY', '')
        if not api_key:
            return None

        chat_model = getattr(settings, 'AI_CHAT_MODEL', 'gpt-4o-mini')
        chat_temperature = getattr(settings, 'AI_CHAT_TEMPERATURE', 0.4)
        max_tokens = getattr(settings, 'AI_CHAT_MAX_TOKENS', 500)
        timeout_seconds = getattr(settings, 'AI_CHAT_TIMEOUT_SECONDS', 25)

        learning_context = cls._get_user_learning_context(user)
        learning_summary = ', '.join(
            [
                f"role={learning_context.get('role') or 'unknown'}",
                f"course={getattr(learning_context.get('course'), 'name', 'unknown')}",
                f"faculty={getattr(learning_context.get('faculty'), 'name', 'unknown')}",
                f"year={learning_context.get('year_of_study') or 'unknown'}",
            ]
        )

        messages = [
            {
                'role': 'system',
                'content': (
                    "You are CampusHub AI, a helpful mini-ChatGPT-style academic assistant "
                    "inside a university platform. Be accurate, warm, and practical. "
                    "Use CampusHub resources when they are available. If a fact is not "
                    "grounded in the provided context, say that clearly instead of making it up. "
                    "Keep answers concise but useful, and suggest next steps when helpful.\n\n"
                    f"Student context: {learning_summary}\n"
                    f"CampusHub knowledge base: {knowledge_match['data']['response'] if knowledge_match else 'None'}\n"
                    f"Retrieved resource context:\n{context_text or 'None'}"
                ),
            }
        ]

        for item in (history or [])[-cls.MAX_HISTORY_FOR_LLM:]:
            messages.append({'role': item.role, 'content': item.content})
        messages.append({'role': 'user', 'content': message})

        payload = {
            'model': chat_model,
            'messages': messages,
            'temperature': chat_temperature,
            'max_tokens': max_tokens,
        }

        req = urlrequest.Request(
            cls.OPENAI_CHAT_COMPLETIONS_URL,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            method='POST',
        )

        try:
            with urlrequest.urlopen(req, timeout=timeout_seconds) as response:
                data = json.loads(response.read().decode('utf-8'))
        except (urlerror.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            logger.warning('OpenAI chat request failed: %s', exc)
            return None

        choices = data.get('choices') or []
        if not choices:
            return None

        content = (choices[0].get('message') or {}).get('content')
        if isinstance(content, str):
            return content.strip()
        return None

    @classmethod
    def _dedupe_actions(cls, actions: List[str]) -> List[str]:
        """Preserve action order while removing duplicates and blanks."""
        deduped: List[str] = []
        seen = set()

        for action in actions:
            normalized = (action or '').strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
        return deduped[:4]

    @classmethod
    def _build_resource_search_response(cls, message: str, user=None) -> ChatResponse:
        """Return a grounded response listing relevant resources."""
        resource_matches = cls._get_resource_matches(message, user=user, limit=5)
        if not resource_matches:
            return ChatResponse(
                message=(
                    "I couldn’t find a strong CampusHub match for that yet. "
                    "Try a course name, unit name, or resource type like notes, slides, or past papers."
                ),
                suggested_actions=cls._dedupe_actions([
                    'Find notes for my course',
                    'Show trending resources',
                    'Create a learning path',
                ]),
                metadata={
                    'intent': 'resource_search',
                    'mode': 'local',
                    'matches_found': 0,
                },
            )

        sources = [
            cls._resource_to_source(result, resource)
            for result, resource in resource_matches[: cls.MAX_SOURCE_COUNT]
        ]

        lines = ["I found these CampusHub resources that look relevant:"]
        for index, (result, resource) in enumerate(resource_matches[:3], start=1):
            descriptor = ' • '.join(
                [
                    resource.resource_type.replace('_', ' ').title(),
                    resource.course.name if resource.course else '',
                    resource.unit.name if resource.unit else '',
                ]
            ).strip(' •')
            lines.append(
                f"{index}. {resource.title}"
                + (f" ({descriptor})" if descriptor else '')
                + (f" - {resource.description[:120]}" if resource.description else '')
            )

        top_title = resource_matches[0][1].title
        return ChatResponse(
            message='\n'.join(lines),
            sources=sources,
            suggested_actions=cls._dedupe_actions([
                f"Summarize {top_title}",
                'Recommend more like this',
                'Create a learning path',
                'How do I download it?',
            ]),
            metadata={
                'intent': 'resource_search',
                'mode': 'local',
                'matches_found': len(resource_matches),
            },
        )

    @classmethod
    def _build_recommendations_response(cls, user=None) -> ChatResponse:
        """Return personalized recommendations."""
        if not user:
            return ChatResponse(
                message=(
                    "I can personalize recommendations once you’re signed in. "
                    "For now, try asking me to find notes, slides, or past papers for a subject."
                ),
                suggested_actions=cls._dedupe_actions([
                    'Find notes for Data Structures',
                    'Show trending resources',
                ]),
                metadata={'intent': 'recommendations', 'mode': 'local', 'matches_found': 0},
            )

        recommendations = RecommendationService.get_user_recommendations(user=user, limit=4)
        if not recommendations:
            return ChatResponse(
                message=(
                    "I don’t have enough activity yet to personalize recommendations. "
                    "Download a few resources or set your course profile, then I can be more specific."
                ),
                suggested_actions=cls._dedupe_actions([
                    'Find notes for my course',
                    'Create a learning path',
                ]),
                metadata={'intent': 'recommendations', 'mode': 'local', 'matches_found': 0},
            )

        lines = ["Here are my top recommendations for you right now:"]
        for index, item in enumerate(recommendations[:4], start=1):
            lines.append(f"{index}. {item.title} - {item.reason}")

        return ChatResponse(
            message='\n'.join(lines),
            sources=[
                {
                    'id': item.id,
                    'title': item.title,
                    'subtitle': item.reason,
                    'route': f"/(student)/resource/{item.id}",
                    'type': item.metadata.get('resource_type'),
                    'score': round(item.score, 3),
                }
                for item in recommendations[: cls.MAX_SOURCE_COUNT]
            ],
            suggested_actions=cls._dedupe_actions([
                'Create a learning path',
                'Recommend more like this',
                'Find notes for my next unit',
            ]),
            metadata={
                'intent': 'recommendations',
                'mode': 'local',
                'matches_found': len(recommendations),
            },
        )

    @classmethod
    def _build_learning_path_response(cls, user=None) -> ChatResponse:
        """Return a concise learning path based on the current user context."""
        if not user:
            return ChatResponse(
                message="I can build a learning path once I know your course profile.",
                suggested_actions=cls._dedupe_actions([
                    'Recommend resources for me',
                    'Find notes for Data Structures',
                ]),
                metadata={'intent': 'learning_path', 'mode': 'local', 'matches_found': 0},
            )

        path = RecommendationService.get_learning_path(user=user)
        if not path.get('courses'):
            return ChatResponse(
                message=(
                    "I couldn’t build a learning path yet because your course or units are missing. "
                    "Update your profile or ask me for resources by subject instead."
                ),
                suggested_actions=cls._dedupe_actions([
                    'Recommend resources for me',
                    'Find notes for my course',
                ]),
                metadata={'intent': 'learning_path', 'mode': 'local', 'matches_found': 0},
            )

        lines = [
            f"I mapped a learning path with {path['resources_count']} resources across {len(path['courses'])} units.",
            f"Estimated study time: about {path['total_hours']} hours.",
            '',
        ]
        sources: List[Dict[str, Any]] = []

        for item in path['courses'][:3]:
            lines.append(
                f"- {item['unit_code']} {item['unit_name']}: "
                f"{len(item['resources'])} resources, ~{item['estimated_hours']} hours"
            )
            for resource in item['resources'][:1]:
                sources.append(
                    {
                        'id': resource['id'],
                        'title': resource['title'],
                        'subtitle': item['unit_name'],
                        'route': f"/(student)/resource/{resource['id']}",
                        'type': resource['type'],
                    }
                )

        return ChatResponse(
            message='\n'.join(lines).strip(),
            sources=sources[: cls.MAX_SOURCE_COUNT],
            suggested_actions=cls._dedupe_actions([
                'Recommend resources for me',
                'Summarize the first resource',
                'Find notes for my next unit',
            ]),
            metadata={
                'intent': 'learning_path',
                'mode': 'local',
                'matches_found': len(path.get('courses', [])),
            },
        )

    @classmethod
    def _build_summary_response(cls, message: str, user=None) -> ChatResponse:
        """Summarize matching resources or inline text."""
        resource_matches = cls._get_resource_matches(message, user=user, limit=3)
        if resource_matches:
            _, resource = resource_matches[0]
            text_to_summarize = ' '.join(
                filter(
                    None,
                    [
                        resource.ai_summary or '',
                        resource.description or '',
                        (resource.ocr_text or '')[:3000],
                    ],
                )
            ) or resource.title
            summary = SummarizationService.summarize_text(text_to_summarize, max_length=180)
            return ChatResponse(
                message=f"Here’s a quick summary of {resource.title}:\n\n{summary.summary}",
                sources=[cls._resource_to_source(resource_matches[0][0], resource)],
                suggested_actions=cls._dedupe_actions([
                    'Give me the key points',
                    f"Find more like {resource.title}",
                    'Create a learning path',
                ]),
                metadata={
                    'intent': 'summary',
                    'mode': 'local',
                    'matches_found': len(resource_matches),
                },
            )

        inline_text = re.sub(
            r'^(please\s+)?(summarize|summary|tl;dr|give me the key points for)\s*',
            '',
            message,
            flags=re.IGNORECASE,
        ).strip()
        if len(inline_text.split()) >= 30:
            summary = SummarizationService.summarize_text(inline_text, max_length=180)
            return ChatResponse(
                message=summary.summary,
                suggested_actions=cls._dedupe_actions([
                    'Give me the key points',
                    'Make it shorter',
                ]),
                metadata={'intent': 'summary', 'mode': 'local', 'matches_found': 0},
            )

        return ChatResponse(
            message=(
                "Tell me which resource to summarize, or paste a longer block of text and I’ll condense it for you."
            ),
            suggested_actions=cls._dedupe_actions([
                'Summarize this PDF I downloaded',
                'Find notes for Data Structures',
            ]),
            metadata={'intent': 'summary', 'mode': 'local', 'matches_found': 0},
        )

    @classmethod
    def _build_contextual_response(
        cls,
        message: str,
        user=None,
        history: Optional[List[ChatMessage]] = None,
        knowledge_match: Optional[Dict[str, Any]] = None,
    ) -> ChatResponse:
        """Handle general chat with retrieval grounding and optional LLM support."""
        resource_matches = cls._get_resource_matches(message, user=user, limit=4)
        sources = [
            cls._resource_to_source(result, resource)
            for result, resource in resource_matches[: cls.MAX_SOURCE_COUNT]
        ]
        resource_context = cls._resource_context_text(resource_matches)

        llm_message = cls._call_openai_chat(
            message=message,
            user=user,
            history=history,
            context_text=resource_context,
            knowledge_match=knowledge_match,
        )
        if llm_message:
            return ChatResponse(
                message=llm_message,
                sources=sources,
                suggested_actions=cls._dedupe_actions([
                    'Explain this more simply',
                    'Summarize the best resource',
                    'Create a learning path',
                ]),
                metadata={
                    'intent': 'general',
                    'mode': 'openai',
                    'matches_found': len(resource_matches),
                },
            )

        if knowledge_match:
            return ChatResponse(
                message=knowledge_match['data']['response'],
                sources=sources,
                suggested_actions=cls._dedupe_actions(
                    knowledge_match['data'].get('actions', [])
                    + ['Find resources for this topic']
                ),
                metadata={
                    'intent': 'platform_help',
                    'mode': 'local',
                    'knowledge_base_key': knowledge_match['key'],
                    'matches_found': len(resource_matches),
                },
            )

        if resource_matches:
            top_resource = resource_matches[0][1]
            explanation_bits = []
            if top_resource.ai_summary:
                explanation_bits.append(top_resource.ai_summary.strip())
            if top_resource.description:
                explanation_bits.append(top_resource.description.strip())
            if not explanation_bits and top_resource.ocr_text:
                explanation_bits.append(top_resource.ocr_text[:500].strip())

            explanation = explanation_bits[0] if explanation_bits else (
                "I found a relevant CampusHub resource, but it doesn’t have enough extracted text yet for a detailed explanation."
            )

            return ChatResponse(
                message=(
                    f"Based on what’s in CampusHub, the strongest match is {top_resource.title}.\n\n"
                    f"{explanation}\n\n"
                    "If you want, I can summarize it, find similar material, or help build a study plan around it."
                ),
                sources=sources,
                suggested_actions=cls._dedupe_actions([
                    f"Summarize {top_resource.title}",
                    'Find more like this',
                    'Create a learning path',
                ]),
                metadata={
                    'intent': 'general',
                    'mode': 'local',
                    'matches_found': len(resource_matches),
                },
            )

        return ChatResponse(
            message=(
                "I can help with CampusHub resources, course recommendations, summaries, and study planning. "
                "Ask me to find notes, explain a topic, summarize a document, or suggest what to study next."
            ),
            suggested_actions=cls._dedupe_actions([
                'Find notes for Data Structures',
                'Recommend resources for me',
                'Create a learning path',
                'How do I upload a resource?',
            ]),
            metadata={'intent': 'general', 'mode': 'local', 'matches_found': 0},
        )

    @classmethod
    def process_message(cls, user_id: str, message: str, user=None) -> ChatResponse:
        """
        Process a user message and generate a response.
        
        Args:
            user_id: Unique user identifier
            message: User's message
            
        Returns:
            ChatResponse with message, sources, and suggested actions
        """
        normalized_message = cls._normalize_message(message)
        if not normalized_message:
            return ChatResponse(
                message='Send a question or topic and I will help from there.',
                suggested_actions=['Find notes for Data Structures', 'How do I upload a resource?'],
                metadata={'intent': 'general', 'mode': 'local', 'matches_found': 0},
            )
        
        # Initialize conversation context for user
        if user_id not in cls.conversation_context:
            cls.conversation_context[user_id] = []
        
        # Add user message to context
        cls.conversation_context[user_id].append(ChatMessage(
            role='user',
            content=message
        ))
        history = cls.conversation_context[user_id]
        knowledge_match = cls._match_knowledge_base(normalized_message)
        intent = cls._detect_intent(normalized_message, knowledge_match=knowledge_match)

        if intent == 'greeting':
            response = ChatResponse(
                message=(
                    "Hi! I’m your CampusHub AI assistant. I can find course resources, "
                    "summarize material, recommend what to study next, and answer platform questions."
                ),
                suggested_actions=cls._dedupe_actions([
                    'Find notes for Data Structures',
                    'Recommend resources for me',
                    'Create a learning path',
                    'How do I upload a resource?',
                ]),
                metadata={'intent': 'greeting', 'mode': 'local', 'matches_found': 0},
            )
        elif intent == 'platform_help' and knowledge_match:
            response = ChatResponse(
                message=knowledge_match['data']['response'],
                suggested_actions=cls._dedupe_actions(knowledge_match['data'].get('actions', [])),
                metadata={
                    'intent': 'platform_help',
                    'mode': 'local',
                    'knowledge_base_key': knowledge_match['key'],
                    'matches_found': 0,
                },
            )
        elif intent == 'resource_search':
            response = cls._build_resource_search_response(message, user=user)
        elif intent == 'recommendations':
            response = cls._build_recommendations_response(user=user)
        elif intent == 'learning_path':
            response = cls._build_learning_path_response(user=user)
        elif intent == 'summary':
            response = cls._build_summary_response(message, user=user)
        else:
            response = cls._build_contextual_response(
                message,
                user=user,
                history=history,
                knowledge_match=knowledge_match,
            )

        response.metadata = {
            **response.metadata,
            'user_id': user_id,
            'intent': response.metadata.get('intent', intent),
        }

        cls.conversation_context[user_id].append(
            ChatMessage(role='assistant', content=response.message)
        )
        cls._trim_context(user_id)
        return response

    @classmethod
    def clear_context(cls, user_id: str):
        """Clear conversation context for a user."""
        if user_id in cls.conversation_context:
            del cls.conversation_context[user_id]


class SummarizationService:
    """
    Document summarization service using AI.
    
    Provides:
    - Extractive summarization
    - Key point extraction
    - Reading time estimation
    - Text simplification
    """

    @classmethod
    def summarize_text(
        cls,
        text: str,
        max_length: int = 200,
        summary_type: str = 'auto'
    ) -> SummaryResult:
        """
        Generate a summary of the given text.
        
        Args:
            text: Input text to summarize
            max_length: Maximum length of summary in words
            summary_type: Type of summary ('auto', 'brief', 'detailed')
            
        Returns:
            SummaryResult with summary, key points, and metadata
        """
        if not text or len(text.strip()) < 50:
            return SummaryResult(
                summary="Text too short to summarize.",
                key_points=[],
                word_count=len(text.split()),
                reading_time_minutes=0,
                language='en'
            )
        
        # Calculate reading time (average 200 words per minute)
        word_count = len(text.split())
        reading_time = word_count / 200
        
        # Extract sentences
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
        
        if not sentences:
            return SummaryResult(
                summary=text[:max_length],
                key_points=[],
                word_count=word_count,
                reading_time_minutes=reading_time,
                language='en'
            )
        
        # Score sentences based on:
        # 1. Position (first sentences are important)
        # 2. Length (medium length is better)
        # 3. Keywords (words that appear frequently)
        
        # Get keyword frequencies
        words = re.findall(r'\b\w+\b', text.lower())
        words = [w for w in words if w not in SemanticSearchService.STOPWORDS and len(w) > 3]
        word_freq = {}
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        # Score each sentence
        scored_sentences = []
        for i, sentence in enumerate(sentences):
            score = 0
            
            # Position score (favor beginning)
            position_score = 1.0 - (i / len(sentences)) * 0.5
            score += position_score
            
            # Length score (favor medium length 20-100 chars)
            length = len(sentence)
            if 20 <= length <= 100:
                score += 0.3
            elif length < 10:
                score -= 0.2
            
            # Keyword score
            sentence_words = re.findall(r'\b\w+\b', sentence.lower())
            keyword_score = sum(word_freq.get(w, 0) for w in sentence_words) / max(len(sentence_words), 1)
            score += min(keyword_score / 10, 0.5)  # Cap keyword contribution
            
            scored_sentences.append((sentence, score))
        
        # Sort by score and select top sentences
        scored_sentences.sort(key=lambda x: x[1], reverse=True)
        
        # Determine summary length based on type
        if summary_type == 'brief':
            num_sentences = max(2, len(sentences) // 4)
        elif summary_type == 'detailed':
            num_sentences = max(4, len(sentences) // 2)
        else:  # auto
            num_sentences = max(3, len(sentences) // 3)
        
        # Get top sentences and sort by original order
        top_sentences = scored_sentences[:num_sentences]
        top_sentences.sort(key=lambda x: sentences.index(x[0]) if x[0] in sentences else 0)
        
        summary = '. '.join([s[0] for s in top_sentences])
        if not summary.endswith('.'):
            summary += '.'
        
        # Extract key points (top 5 scored sentences)
        key_points = [s[0] for s in scored_sentences[:5]]
        
        # Detect language (simplified)
        language = 'en'  # Default to English
        
        return SummaryResult(
            summary=summary,
            key_points=key_points,
            word_count=word_count,
            reading_time_minutes=round(reading_time, 1),
            language=language
        )

    @classmethod
    def summarize_resource(cls, resource_id: str) -> SummaryResult:
        """
        Generate a summary for a resource.
        
        Args:
            resource_id: ID of the resource to summarize
            
        Returns:
            SummaryResult
        """
        from apps.resources.models import Resource
        
        try:
            resource = Resource.objects.get(id=resource_id)
            text = f"{resource.title}. {resource.description or ''}"
            
            # If there's a file content, that would be summarized too
            # For now, summarize title and description
            
            return cls.summarize_text(text)
        except Resource.DoesNotExist:
            return SummaryResult(
                summary="Resource not found",
                key_points=[],
                word_count=0,
                reading_time_minutes=0,
                language='en'
            )


# Convenience functions for easy import
def semantic_search(query: str, **kwargs) -> List[SearchResult]:
    """Wrapper for semantic search."""
    return SemanticSearchService.search_resources(query, SearchType.SEMANTIC, **kwargs)

def get_recommendations(user, **kwargs) -> List[Recommendation]:
    """Wrapper for getting recommendations."""
    return RecommendationService.get_user_recommendations(user, **kwargs)

def chat_with_bot(user_id: str, message: str) -> ChatResponse:
    """Wrapper for chatbot."""
    return ChatbotService.process_message(user_id, message)

def summarize(text: str, **kwargs) -> SummaryResult:
    """Wrapper for summarization."""
    return SummarizationService.summarize_text(text, **kwargs)


class StudyGoalService:
    """
    AI-powered study goal generation service.
    
    Generates personalized study goals based on:
    - Student's current progress and grades
    - Learning patterns and analytics
    - Upcoming exams and assignments
    - Weak areas identified from performance
    """

    @dataclass
    class GeneratedGoal:
        """A generated study goal."""
        title: str
        description: str
        goal_type: str
        priority: str
        target_hours: Optional[float]
        target_topics: List[str]
        weak_areas: List[str]
        recommendations: Dict[str, Any]
        start_date: Optional[datetime]
        target_date: Optional[datetime]
        milestones: List[Dict[str, Any]]

    @classmethod
    def analyze_student_performance(cls, user) -> Dict:
        """
        Analyze student's performance data.
        
        Returns:
            Dict with performance metrics and weak areas
        """
        from apps.analytics.models import AnalyticsEvent
        from apps.accounts.models import User
        
        analysis = {
            'total_study_hours': 0,
            'resources_downloaded': 0,
            'resources_viewed': 0,
            'average_session_duration': 0,
            'weak_areas': [],
            'strong_areas': [],
            'recent_activity': [],
            'completion_rate': 0,
        }
        
        try:
            # Get study time from analytics
            study_events = AnalyticsEvent.objects.filter(
                user=user,
                event_type__in=['resource_view', 'resource_download']
            ).order_by('-timestamp')[:100]
            
            total_duration = 0
            resource_ids = set()
            
            for event in study_events:
                if event.duration_seconds:
                    total_duration += event.duration_seconds
                if event.resource_id:
                    resource_ids.add(event.resource_id)
            
            analysis['total_study_hours'] = round(total_duration / 3600, 1)
            analysis['resources_viewed'] = len(study_events)
            analysis['resources_downloaded'] = len(resource_ids)
            
            # Calculate average session duration
            if study_events:
                analysis['average_session_duration'] = round(
                    total_duration / max(len(study_events), 1) / 60, 1
                )
            
            # Get recent activity
            recent = AnalyticsEvent.objects.filter(
                user=user
            ).order_by('-timestamp')[:10]
            
            analysis['recent_activity'] = [
                {
                    'type': e.event_type,
                    'timestamp': e.timestamp.isoformat(),
                }
                for e in recent
            ]
            
            # Calculate completion rate (completed vs total events)
            completed = AnalyticsEvent.objects.filter(
                user=user,
                event_type='resource_download'
            ).count()
            
            total = AnalyticsEvent.objects.filter(
                user=user,
                event_type__in=['resource_view', 'resource_download']
            ).count()
            
            if total > 0:
                analysis['completion_rate'] = round((completed / total) * 100, 1)
            
        except Exception as e:
            logger.warning(f"Error analyzing student performance: {e}")
        
        return analysis

    @classmethod
    def get_upcoming_deadlines(cls, user) -> List[Dict]:
        """
        Get upcoming exams and assignments.
        
        Returns:
            List of upcoming deadlines
        """
        from apps.calendar.models import PersonalSchedule

        deadlines = []
        now = timezone.now()
        
        try:
            # PersonalSchedule stores user-specific exams and assignment deadlines.
            events = PersonalSchedule.objects.filter(
                user=user,
                date__gte=now.date(),
                category__in=['exam', 'assignment']
            ).order_by('date', 'start_time')[:10]
            
            for event in events:
                days_until = (event.date - now.date()).days
                deadlines.append({
                    'id': str(event.id),
                    'title': event.title,
                    'type': event.category,
                    'date': event.date.isoformat(),
                    'days_until': days_until,
                })
        except Exception as e:
            logger.warning(f"Error getting upcoming deadlines: {e}")
        
        return deadlines

    @classmethod
    def get_user_courses_and_units(cls, user) -> Dict:
        """
        Get user's enrolled courses and units.
        
        Returns:
            Dict with courses and units
        """
        from apps.courses.models import Unit
        
        result = {
            'courses': [],
            'units': [],
        }
        
        try:
            # Get user profile - user has course directly on User model
            user_course = getattr(user, 'course', None)
            if user_course:
                result['courses'].append({
                    'id': str(user_course.id),
                    'name': user_course.name,
                    'code': user_course.code,
                })
                
                # Get units for this course
                units = Unit.objects.filter(course=user_course, is_active=True)
                for unit in units:
                    result['units'].append({
                        'id': str(unit.id),
                        'name': unit.name,
                        'code': unit.code,
                        'course_id': str(user_course.id),
                        'semester': unit.semester,
                    })
        except Exception as e:
            logger.warning(f"Error getting user courses: {e}")
        
        return result

    @classmethod
    def identify_weak_areas(cls, user, performance: Dict, units: List) -> List[str]:
        """
        Identify weak areas based on performance and course data.
        
        Returns:
            List of weak areas
        """
        weak_areas = []
        
        # Analyze based on completion rate
        if performance.get('completion_rate', 0) < 50:
            weak_areas.append('Study consistency')
        
        if performance.get('average_session_duration', 0) < 15:
            weak_areas.append('Deep focus sessions')
        
        # Add units as potential weak areas
        # In a real implementation, this would analyze actual grades
        if units:
            # Randomly identify some units as weak for demonstration
            # In production, this would use actual grade data
            for unit in units[:3]:
                weak_areas.append(f"{unit.get('name', 'Unknown unit')}")
        
        return list(set(weak_areas))[:5]

    @classmethod
    def generate_weekly_targets(
        cls,
        performance: Dict,
        weak_areas: List[str]
    ) -> Dict:
        """
        Generate weekly study targets.
        
        Returns:
            Dict with weekly targets
        """
        # Base weekly hours on past performance
        base_hours = performance.get('total_study_hours', 0)
        
        # Suggest 10-20 hours per week for students
        if base_hours < 5:
            recommended_hours = 10
        elif base_hours < 20:
            recommended_hours = 15
        else:
            recommended_hours = min(25, base_hours + 5)
        
        # Generate topics based on weak areas
        topics = []
        for area in weak_areas[:3]:
            topics.append(f"Review {area} fundamentals")
            topics.append(f"Practice exercises on {area}")
        
        return {
            'target_hours': recommended_hours,
            'daily_hours': round(recommended_hours / 7, 1),
            'topics': topics[:5],
            'sessions_per_week': 5,
        }

    @classmethod
    def generate_milestones(
        cls,
        deadlines: List[Dict],
        goal_type: str
    ) -> List[Dict]:
        """
        Generate milestones based on upcoming deadlines.
        
        Returns:
            List of milestones
        """
        milestones = []
        
        for deadline in deadlines[:5]:
            days_until = deadline.get('days_until', 0)
            
            # Create milestone based on deadline type
            milestone = {
                'title': deadline['title'],
                'type': deadline['type'],
                'due_date': deadline['date'],
                'days_until': days_until,
            }
            
            # Add preparation milestones for exams
            if deadline['type'] in ['exam', 'test', 'quiz']:
                if days_until > 7:
                    milestones.append({
                        **milestone,
                        'title': f"Start preparing for {deadline['title']}",
                        'type': 'checkpoint',
                        'due_date': (datetime.strptime(deadline['date'], '%Y-%m-%d') - timedelta(days=7)).date().isoformat(),
                        'days_until': days_until - 7,
                    })
            
            milestones.append(milestone)
        
        return milestones

    @classmethod
    def generate_study_goals(
        cls,
        user,
        goal_type: str = 'all'
    ) -> List[GeneratedGoal]:
        """
        Generate personalized study goals for a student.
        
        Args:
            user: The user to generate goals for
            goal_type: Type of goals to generate ('short_term', 'medium_term', 'long_term', 'subject_specific', 'all')
            
        Returns:
            List of GeneratedGoal objects
        """
        goals = []
        
        # Analyze student performance
        performance = cls.analyze_student_performance(user)
        
        # Get upcoming deadlines
        deadlines = cls.get_upcoming_deadlines(user)
        
        # Get user's courses and units
        course_data = cls.get_user_courses_and_units(user)
        units = course_data.get('units', [])
        
        # Identify weak areas
        weak_areas = cls.identify_weak_areas(user, performance, units)
        
        # Generate weekly targets
        weekly_targets = cls.generate_weekly_targets(performance, weak_areas)
        
        # Generate short-term goals (daily/weekly)
        if goal_type in ['all', 'short_term']:
            now = timezone.now()
            week_end = now + timedelta(days=7)
            
            goals.append(cls.GeneratedGoal(
                title="Weekly Study Target",
                description=f"Study for {weekly_targets['target_hours']} hours this week. "
                           f"Focus on: {', '.join(weekly_targets['topics'][:3])}",
                goal_type="short_term",
                priority="high" if weak_areas else "medium",
                target_hours=weekly_targets['target_hours'],
                target_topics=weekly_targets['topics'],
                weak_areas=weak_areas,
                recommendations={
                    'daily_schedule': {
                        'monday': f"{weekly_targets['daily_hours']} hours - {weekly_targets['topics'][0] if weekly_targets['topics'] else 'General study'}",
                        'tuesday': f"{weekly_targets['daily_hours']} hours - {weekly_targets['topics'][1] if len(weekly_targets['topics']) > 1 else 'Practice problems'}",
                        'wednesday': f"{weekly_targets['daily_hours']} hours - {weekly_targets['topics'][2] if len(weekly_targets['topics']) > 2 else 'Review notes'}",
                        'thursday': f"{weekly_targets['daily_hours']} hours - Weak area focus",
                        'friday': f"{weekly_targets['daily_hours']} hours - Practice and revision",
                        'saturday': f"{weekly_targets['daily_hours'] * 1.5} hours - Full mock exam practice",
                        'sunday': f"{weekly_targets['daily_hours'] * 0.5} hours - Light review",
                    },
                    'focus_areas': weak_areas,
                    'suggested_resources': cls._get_suggested_resources(units, weak_areas),
                },
                start_date=now.date(),
                target_date=week_end.date(),
                milestones=cls.generate_milestones(deadlines, 'short_term'),
            ))
        
        # Generate medium-term goals (monthly)
        if goal_type in ['all', 'medium_term']:
            now = timezone.now()
            month_end = now + timedelta(days=30)
            
            goals.append(cls.GeneratedGoal(
                title="Monthly Learning Objective",
                description=f"Complete all core topics in your enrolled courses. "
                           f"Target: Master {len(weekly_targets['topics']) * 4} topics this month.",
                goal_type="medium_term",
                priority="medium",
                target_hours=weekly_targets['target_hours'] * 4,
                target_topics=weekly_targets['topics'] * 4,
                weak_areas=weak_areas,
                recommendations={
                    'weekly_breakdown': [
                        {'week': 1, 'focus': 'Foundation building', 'hours': weekly_targets['target_hours']},
                        {'week': 2, 'focus': 'Intermediate concepts', 'hours': weekly_targets['target_hours']},
                        {'week': 3, 'focus': 'Advanced topics', 'hours': weekly_targets['target_hours']},
                        {'week': 4, 'focus': 'Review and practice', 'hours': weekly_targets['target_hours']},
                    ],
                    'assessment_dates': [d['date'] for d in deadlines[:3]],
                },
                start_date=now.date(),
                target_date=month_end.date(),
                milestones=cls.generate_milestones(deadlines, 'medium_term'),
            ))
        
        # Generate long-term goals (semester/course completion)
        if goal_type in ['all', 'long_term']:
            now = timezone.now()
            semester_end = now + timedelta(days=120)  # ~4 months
            
            course_names = [c['name'] for c in course_data.get('courses', [])]
            
            goals.append(cls.GeneratedGoal(
                title="Semester Completion Goal",
                description=f"Successfully complete your {', '.join(course_names) if course_names else 'courses'} "
                           f"with a target grade of B or higher.",
                goal_type="long_term",
                priority="high",
                target_hours=weekly_targets['target_hours'] * 16,  # 16 weeks
                target_topics=[u['name'] for u in units] if units else ['Course completion'],
                weak_areas=weak_areas,
                recommendations={
                    'semester_plan': {
                        'months': [
                            {'month': 1, 'focus': 'Course introduction and basics'},
                            {'month': 2, 'focus': 'Core concepts and fundamentals'},
                            {'month': 3, 'focus': 'Advanced topics and applications'},
                            {'month': 4, 'focus': 'Exam preparation and review'},
                        ]
                    },
                    'grade_targets': {
                        'assignment_score': 85,
                        'exam_score': 80,
                        'participation': 90,
                    },
                },
                start_date=now.date(),
                target_date=semester_end.date(),
                milestones=cls.generate_milestones(deadlines, 'long_term'),
            ))
        
        # Generate subject-specific goals
        if goal_type in ['all', 'subject_specific']:
            for unit in units[:3]:  # Limit to 3 units
                goals.append(cls.GeneratedGoal(
                    title=f"Master {unit.get('name', 'Subject')}",
                    description=f"Achieve proficiency in {unit.get('name', 'this subject')} "
                               f"through focused study and practice.",
                    goal_type="subject_specific",
                    priority="medium",
                    target_hours=20,
                    target_topics=[f"{unit.get('name')} - Topic {i}" for i in range(1, 6)],
                    weak_areas=[unit.get('name', '')] if unit.get('name') in weak_areas else [],
                    recommendations={
                        'unit_code': unit.get('code'),
                        'semester': unit.get('semester'),
                        'study_resources': cls._get_suggested_resources([unit], []),
                    },
                    start_date=timezone.now().date(),
                    target_date=(timezone.now() + timedelta(days=30)).date(),
                    milestones=[],
                ))
        
        return goals

    @classmethod
    def _get_suggested_resources(cls, units: List, weak_areas: List) -> List[Dict]:
        """
        Get suggested resources for study.
        
        Returns:
            List of suggested resources
        """
        from apps.resources.models import Resource
        
        resources = []
        
        try:
            # Get popular resources for the units
            unit_ids = [u['id'] for u in units[:3]]
            
            if unit_ids:
                popular_resources = Resource.objects.filter(
                    unit_id__in=unit_ids,
                    status='approved'
                ).order_by('-download_count', '-average_rating')[:5]
                
                for r in popular_resources:
                    resources.append({
                        'id': str(r.id),
                        'title': r.title,
                        'type': r.resource_type,
                        'rating': r.average_rating,
                    })
        except Exception as e:
            logger.warning(f"Error getting suggested resources: {e}")
        
        return resources

    @classmethod
    def save_generated_goals(cls, user, goals: List[GeneratedGoal]) -> List:
        """
        Save generated goals to the database.
        
        Returns:
            List of saved StudyGoal objects
        """
        from apps.ai.models import StudyGoal, StudyGoalMilestone
        
        saved_goals = []
        
        for goal in goals:
            # Create the goal
            study_goal = StudyGoal.objects.create(
                user=user,
                title=goal.title,
                description=goal.description,
                goal_type=goal.goal_type,
                priority=goal.priority,
                target_hours=goal.target_hours,
                target_topics=goal.target_topics,
                weak_areas=goal.weak_areas,
                ai_recommendations=goal.recommendations,
                start_date=goal.start_date,
                target_date=goal.target_date,
                is_auto_generated=True,
                generation_context={
                    'generated_at': timezone.now().isoformat(),
                    'goal_type': goal.goal_type,
                }
            )
            
            # Create milestones
            for milestone_data in goal.milestones:
                StudyGoalMilestone.objects.create(
                    study_goal=study_goal,
                    title=milestone_data.get('title', ''),
                    description=milestone_data.get('description', ''),
                    milestone_type=milestone_data.get('type', 'checkpoint'),
                    due_date=milestone_data.get('due_date'),
                )
            
            saved_goals.append(study_goal)
        
        return saved_goals

    @classmethod
    def get_goal_adjustments(cls, study_goal) -> Dict:
        """
        Suggest adjustments based on progress.
        
        Returns:
            Dict with adjustment recommendations
        """
        adjustments = {
            'suggestions': [],
            'new_target_hours': None,
            'new_deadline': None,
            'additional_topics': [],
        }
        
        # Analyze progress
        if study_goal.target_hours and study_goal.completed_hours:
            progress_ratio = study_goal.completed_hours / study_goal.target_hours
            
            # If behind schedule
            if progress_ratio < 0.5 and study_goal.progress < 50:
                adjustments['suggestions'].append(
                    "You're behind schedule. Consider increasing daily study time."
                )
                adjustments['new_target_hours'] = study_goal.target_hours * 1.2
            
            # If on track
            elif progress_ratio >= 0.8:
                adjustments['suggestions'].append(
                    "Great progress! You can take on additional challenges."
                )
                adjustments['additional_topics'] = [
                    "Advanced practice problems",
                    "Peer teaching sessions",
                ]
        
        # Check deadline proximity
        if study_goal.target_date:
            days_until = (study_goal.target_date - timezone.now().date()).days
            
            if days_until < 7 and study_goal.progress < 70:
                adjustments['suggestions'].append(
                    f"Deadline approaching ({days_until} days). Focus on key topics."
                )
                adjustments['additional_topics'] = study_goal.target_topics[:3]
        
        return adjustments

    @classmethod
    def create_reminder(cls, study_goal, reminder_type: str, days_before: int = 1):
        """
        Create a reminder for a study goal.
        """
        from apps.ai.models import GoalReminder
        from datetime import timedelta
        
        if not study_goal.target_date:
            return None
        
        scheduled_date = study_goal.target_date - timedelta(days=days_before)
        scheduled_at = timezone.make_aware(
            datetime.combine(scheduled_date, datetime.min.time())
        )
        
        messages = {
            'daily': f"Don't forget to study today! Goal: {study_goal.title}",
            'weekly': f"Weekly check-in: You're at {study_goal.progress}% for {study_goal.title}",
            'deadline': f"Deadline approaching for: {study_goal.title}",
            'overdue': f"Goal overdue: {study_goal.title}. Time to catch up!",
        }
        
        return GoalReminder.objects.create(
            study_goal=study_goal,
            reminder_type=reminder_type,
            scheduled_at=scheduled_at,
            message=messages.get(reminder_type, f"Reminder for {study_goal.title}"),
        )
