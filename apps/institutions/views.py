"""
Views for Institutions API
"""

from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from .models import Institution, InstitutionAdmin, Department, InstitutionInvitation
from .services import MultiTenantService, InstitutionStatisticsService
from .serializers import (
    InstitutionSerializer,
    InstitutionAdminSerializer,
    DepartmentSerializer,
    InstitutionInvitationSerializer,
    InstitutionRegistrationSerializer,
    InstitutionApprovalSerializer,
)


class InstitutionListView(generics.ListAPIView):
    """List active institutions (public)"""
    serializer_class = InstitutionSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Institution.objects.filter(
            is_active=True,
            allow_registration=True
        )[:50]


class InstitutionDetailView(generics.RetrieveAPIView):
    """Get institution details"""
    serializer_class = InstitutionSerializer
    permission_classes = [AllowAny]
    queryset = Institution.objects.all()


class MyInstitutionView(generics.RetrieveAPIView):
    """Get user's current institution"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        institution = MultiTenantService.get_user_institution(request.user)
        
        if not institution:
            return Response(
                {'error': 'User does not belong to an institution'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(InstitutionSerializer(institution).data)


class InstitutionAdminsView(generics.ListCreateAPIView):
    """List institution admins or add new admin"""
    permission_classes = [IsAuthenticated]
    serializer_class = InstitutionAdminSerializer

    def get_queryset(self):
        institution_id = self.kwargs.get('institution_id')
        return InstitutionAdmin.objects.filter(
            institution_id=institution_id,
            is_active=True
        ).select_related('user', 'institution')

    def perform_create(self, serializer):
        institution_id = self.kwargs.get('institution_id')
        # Verify the requester is an admin
        # In production, add permission check here


class InstitutionStatsView(generics.RetrieveAPIView):
    """Get institution statistics"""
    permission_classes = [IsAuthenticated]
    serializer_class = InstitutionSerializer

    def retrieve(self, request, institution_id):
        try:
            institution = Institution.objects.get(id=institution_id)
        except Institution.DoesNotExist:
            return Response(
                {'error': 'Institution not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permission
        if not MultiTenantService.is_institution_admin(request.user, institution):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        stats = InstitutionStatisticsService.get_institution_stats(institution)
        return Response(stats)


class DepartmentListView(generics.ListCreateAPIView):
    """List or create departments"""
    permission_classes = [IsAuthenticated]
    serializer_class = DepartmentSerializer

    def get_queryset(self):
        institution_id = self.kwargs.get('institution_id')
        return Department.objects.filter(
            institution_id=institution_id,
            is_active=True
        ).select_related('head')

    def perform_create(self, serializer):
        institution_id = self.kwargs.get('institution_id')
        serializer.save(institution_id=institution_id)


class InvitationListView(generics.ListCreateAPIView):
    """List or create invitations"""
    permission_classes = [IsAuthenticated]
    serializer_class = InstitutionInvitationSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return InstitutionInvitation.objects.none()

        institution_id = self.kwargs.get('institution_id')

        if not institution_id or not self.request.user.is_authenticated:
            return InstitutionInvitation.objects.none()

        # Check permission without constructing an unsaved Institution instance.
        if not MultiTenantService.can_manage_users(self.request.user, institution_id):
            return InstitutionInvitation.objects.none()
        
        return InstitutionInvitation.objects.filter(
            institution_id=institution_id,
            accepted=False
        )

    def perform_create(self, serializer):
        institution_id = self.kwargs.get('institution_id')
        serializer.save(
            invited_by=self.request.user,
            institution_id=institution_id
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def accept_invitation(request):
    """Accept an invitation"""
    token = request.data.get('token')
    
    if not token:
        return Response(
            {'error': 'Token required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    invitation, error = MultiTenantService.accept_invitation(token)
    
    if error:
        return Response(
            {'error': error},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    return Response(
        InstitutionInvitationSerializer(invitation).data,
        status=status.HTTP_200_OK
    )


@api_view(['GET'])
@permission_classes([AllowAny])
def detect_institution(request):
    """Detect institution from email"""
    email = request.query_params.get('email', '')
    
    institution = MultiTenantService.detect_institution_from_email(email)
    
    if not institution:
        return Response({'institution': None})
    
    return Response({
        'institution': InstitutionSerializer(institution).data,
        'requires_verification': institution.require_email_verification,
    })


class InstitutionRegistrationView(generics.CreateAPIView):
    """Register a new institution (public endpoint)"""
    serializer_class = InstitutionRegistrationSerializer
    permission_classes = [AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Create institution (initially inactive pending approval)
        institution = serializer.save(
            is_active=False,  # Requires approval
            is_verified=False,
            allow_registration=True,
        )
        
        # Create the admin user for this institution
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Create admin user with contact email from registration
        user = User.objects.create_user(
            email=request.data.get('contact_email'),
            password=request.data.get('password'),
            full_name=request.data.get('contact_name', ''),
            role='admin',
        )
        
        # Create InstitutionAdmin role
        InstitutionAdmin.objects.create(
            user=user,
            institution=institution,
            role='owner',
            can_manage_users=True,
            can_manage_content=True,
            can_manage_settings=True,
            can_view_analytics=True,
        )
        
        return Response({
            'message': 'Institution registered successfully. Pending approval.',
            'institution': InstitutionSerializer(institution).data,
            'login_url': '/accounts/login/'
        }, status=status.HTTP_201_CREATED)


class InstitutionApprovalView(generics.UpdateAPIView):
    """Approve or reject an institution (admin only)"""
    serializer_class = InstitutionApprovalSerializer
    permission_classes = [IsAuthenticated]
    queryset = Institution.objects.all()
    lookup_field = 'pk'
    
    def perform_update(self, serializer):
        # In production, check if user is super admin
        instance = serializer.save()
        
        # Send approval email (placeholder)
        self.send_approval_email(instance)
    
    def send_approval_email(self, institution):
        """Send approval notification email"""
        # Implementation would send email via Django's email backend
        pass
