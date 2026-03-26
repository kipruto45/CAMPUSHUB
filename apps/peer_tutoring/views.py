"""
Views for Peer Tutoring API
"""

from django.db import models
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import TutoringProfile, TutoringSession, TutoringRequest, TutoringReview, TutoringSubject
from .services import PeerTutoringService
from .serializers import (
    TutoringProfileSerializer,
    TutoringSessionSerializer,
    TutoringRequestSerializer,
    TutoringReviewSerializer,
    TutoringSubjectSerializer,
)


class TutorListView(generics.ListAPIView):
    """List available tutors"""
    serializer_class = TutoringProfileSerializer
    
    def get_queryset(self):
        subject = self.request.query_params.get('subject')
        max_rate = self.request.query_params.get('max_rate')
        
        queryset = TutoringProfile.objects.filter(is_available=True)
        
        if subject:
            queryset = queryset.filter(expertise__contains=[subject])
        
        if max_rate:
            queryset = queryset.filter(hourly_rate__lte=max_rate)
        
        return queryset.select_related('user')[:50]


class MyProfileView(generics.RetrieveUpdateAPIView):
    """Get or update my tutoring profile"""
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        return TutoringProfileSerializer
    
    def get_object(self):
        profile, _ = PeerTutoringService.get_or_create_profile(self.request.user)
        return profile


class SessionListCreateView(generics.ListCreateAPIView):
    """List tutoring sessions or create new one"""
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        return TutoringSessionSerializer
    
    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not self.request.user.is_authenticated:
            return TutoringSession.objects.none()
        user = self.request.user
        return TutoringSession.objects.filter(
            models.Q(tutor__user=user) | models.Q(student=user)
        ).select_related('tutor__user', 'student')
    
    def perform_create(self, serializer):
        # Set student to current user
        serializer.save(student=self.request.user)


class SessionDetailView(generics.RetrieveUpdateAPIView):
    """Get or update a tutoring session"""
    permission_classes = [IsAuthenticated]
    serializer_class = TutoringSessionSerializer
    queryset = TutoringSession.objects.all()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def confirm_session(request, pk):
    """Confirm a session"""
    session = PeerTutoringService.confirm_session(pk)
    if session:
        return Response(TutoringSessionSerializer(session).data)
    return Response({'error': 'Session not found'}, status=404)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_session(request, pk):
    """Start a session"""
    session = PeerTutoringService.start_session(pk)
    if session:
        return Response(TutoringSessionSerializer(session).data)
    return Response({'error': 'Session not found'}, status=404)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_session(request, pk):
    """Complete a session"""
    session = PeerTutoringService.complete_session(pk)
    if session:
        return Response(TutoringSessionSerializer(session).data)
    return Response({'error': 'Session not found'}, status=404)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_review(request, pk):
    """Submit a review for a session"""
    rating = request.data.get('rating')
    comment = request.data.get('comment', '')
    aspects = request.data.get('aspects')
    
    review, error = PeerTutoringService.submit_review(
        pk, request.user, rating, comment, aspects
    )
    
    if error:
        return Response({'error': error}, status=400)
    
    return Response(TutoringReviewSerializer(review).data, status=201)


class RequestListCreateView(generics.ListCreateAPIView):
    """List or create tutoring requests"""
    permission_classes = [IsAuthenticated]
    serializer_class = TutoringRequestSerializer
    
    def get_queryset(self):
        return TutoringRequest.objects.filter(status='open')
    
    def perform_create(self, serializer):
        serializer.save(student=self.request.user)


class SubjectListView(generics.ListAPIView):
    """List available tutoring subjects"""
    serializer_class = TutoringSubjectSerializer
    queryset = TutoringSubject.objects.filter(is_active=True)
