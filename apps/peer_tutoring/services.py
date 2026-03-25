"""
Services for Peer Tutoring
"""

from django.db.models import Avg, Count
from django.utils import timezone
from .models import TutoringProfile, TutoringSession, TutoringRequest, TutoringReview


class PeerTutoringService:
    """Service for peer tutoring operations"""
    
    @staticmethod
    def get_or_create_profile(user):
        """Get or create a tutoring profile for a user"""
        profile, created = TutoringProfile.objects.get_or_create(user=user)
        return profile
    
    @staticmethod
    def find_tutors(subject=None, max_rate=None):
        """Find available tutors"""
        queryset = TutoringProfile.objects.filter(is_available=True)
        
        if subject:
            queryset = queryset.filter(expertise__contains=[subject])
        
        if max_rate is not None:
            queryset = queryset.filter(hourly_rate__lte=max_rate)
        
        return queryset.select_related('user')
    
    @staticmethod
    def get_matching_tutors(subject, student):
        """Get AI-matched tutors for a subject"""
        # Get tutors with expertise in the subject
        tutors = TutoringProfile.objects.filter(
            is_available=True,
            expertise__contains=[subject]
        ).select_related('user')
        
        # Score and rank tutors
        scored_tutors = []
        for tutor in tutors:
            score = 0
            
            # Rating score (0-40 points)
            if tutor.average_rating:
                score += float(tutor.average_rating) * 8
            
            # Experience score (0-30 points)
            score += min(tutor.experience_years * 5, 30)
            
            # Session completion rate (0-30 points)
            if tutor.total_sessions > 0:
                completion_rate = 100  # Would calculate actual rate
                score += completion_rate * 0.3
            
            scored_tutors.append({
                'tutor': tutor,
                'score': score
            })
        
        # Sort by score descending
        scored_tutors.sort(key=lambda x: x['score'], reverse=True)
        
        return [item['tutor'] for item in scored_tutors[:10]]
    
    @staticmethod
    def create_session_request(tutor_id, student, subject, topic, description, scheduled_start, scheduled_end):
        """Create a tutoring session request"""
        from .models import TutoringSession
        
        try:
            tutor = TutoringProfile.objects.get(id=tutor_id, is_available=True)
        except TutoringProfile.DoesNotExist:
            return None, "Tutor not found"
        
        session = TutoringSession.objects.create(
            tutor=tutor,
            student=student,
            subject=subject,
            topic=topic,
            description=description,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            rate=tutor.hourly_rate,
            status='pending'
        )
        
        return session, None
    
    @staticmethod
    def confirm_session(session_id):
        """Confirm a tutoring session"""
        try:
            session = TutoringSession.objects.get(id=session_id)
            session.status = 'confirmed'
            session.save()
            return session
        except TutoringSession.DoesNotExist:
            return None
    
    @staticmethod
    def start_session(session_id):
        """Mark session as in progress"""
        try:
            session = TutoringSession.objects.get(id=session_id)
            session.status = 'in_progress'
            session.actual_start = timezone.now()
            session.save()
            return session
        except TutoringSession.DoesNotExist:
            return None
    
    @staticmethod
    def complete_session(session_id):
        """Complete a tutoring session"""
        try:
            session = TutoringSession.objects.get(id=session_id)
            session.status = 'completed'
            session.actual_end = timezone.now()
            
            # Update tutor stats
            tutor = session.tutor
            duration_hours = session.duration_minutes / 60
            tutor.total_sessions += 1
            tutor.total_hours += duration_hours
            tutor.save()
            
            session.save()
            return session
        except TutoringSession.DoesNotExist:
            return None
    
    @staticmethod
    def submit_review(session_id, reviewer, rating, comment, aspects=None):
        """Submit a review for a tutoring session"""
        try:
            session = TutoringSession.objects.get(id=session_id)
        except TutoringSession.DoesNotExist:
            return None, "Session not found"
        
        # Determine if reviewer is student or tutor
        if session.student == reviewer:
            tutor = session.tutor
        elif session.tutor.user == reviewer:
            # Tutor reviewing student (optional feature)
            return None, "Students cannot be reviewed"
        else:
            return None, "Not authorized to review this session"
        
        review = TutoringReview.objects.create(
            session=session,
            reviewer=reviewer,
            tutor=tutor,
            rating=rating,
            comment=comment,
            knowledge_rating=aspects.get('knowledge', 5) if aspects else 5,
            communication_rating=aspects.get('communication', 5) if aspects else 5,
            patience_rating=aspects.get('patience', 5) if aspects else 5,
        )
        
        # Update tutor's average rating
        avg = TutoringReview.objects.filter(
            tutor=tutor
        ).aggregate(
            avg_rating=Avg('rating')
        )['avg_rating']
        
        tutor.average_rating = avg or rating
        tutor.total_reviews += 1
        tutor.save()
        
        return review, None
    
    @staticmethod
    def create_request(student, subject, topic, description, max_rate=0):
        """Create a tutoring request"""
        from datetime import timedelta
        
        request = TutoringRequest.objects.create(
            student=student,
            subject=subject,
            topic=topic,
            description=description,
            preferred_rate_max=max_rate,
            expires_at=timezone.now() + timedelta(days=7),
        )
        
        return request
    
    @staticmethod
    def match_request_to_tutors(request_id):
        """Find tutors matching a request"""
        try:
            request = TutoringRequest.objects.get(id=request_id)
        except TutoringRequest.DoesNotExist:
            return []
        
        tutors = TutoringProfile.objects.filter(
            is_available=True,
            hourly_rate__lte=request.preferred_rate_max,
            expertise__contains=[request.subject]
        ).select_related('user')
        
        return list(tutors)
