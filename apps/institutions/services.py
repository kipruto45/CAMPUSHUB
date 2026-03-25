"""
Services for Institutions (Multi-Tenant)
"""

import uuid
import secrets
from datetime import timedelta
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import Institution, InstitutionAdmin, Department, InstitutionInvitation

User = get_user_model()


class MultiTenantService:
    """Service for multi-tenant operations"""
    
    @staticmethod
    def get_user_institution(user) -> Institution | None:
        """Get the institution a user belongs to"""
        if hasattr(user, 'institution'):
            return user.institution
        return None
    
    @staticmethod
    def get_user_institutions(user) -> list[Institution]:
        """Get all institutions a user belongs to"""
        admin_roles = InstitutionAdmin.objects.filter(
            user=user,
            is_active=True
        ).select_related('institution')
        
        return [role.institution for role in admin_roles]
    
    @staticmethod
    def is_institution_admin(user, institution) -> bool:
        """Check if user is an admin for an institution"""
        return InstitutionAdmin.objects.filter(
            user=user,
            institution=institution,
            is_active=True
        ).exists()
    
    @staticmethod
    def get_admin_role(user, institution) -> str | None:
        """Get user's admin role for an institution"""
        try:
            admin = InstitutionAdmin.objects.get(
                user=user,
                institution=institution,
                is_active=True
            )
            return admin.role
        except InstitutionAdmin.DoesNotExist:
            return None
    
    @staticmethod
    def can_manage_users(user, institution) -> bool:
        """Check if user can manage users in an institution"""
        try:
            admin = InstitutionAdmin.objects.get(
                user=user,
                institution=institution,
                is_active=True
            )
            return admin.role == 'owner' or admin.can_manage_users
        except InstitutionAdmin.DoesNotExist:
            return False
    
    @staticmethod
    def can_manage_content(user, institution) -> bool:
        """Check if user can manage content in an institution"""
        try:
            admin = InstitutionAdmin.objects.get(
                user=user,
                institution=institution,
                is_active=True
            )
            return admin.role == 'owner' or admin.can_manage_content
        except InstitutionAdmin.DoesNotExist:
            return False
    
    @staticmethod
    def get_institution_queryset(user, base_queryset):
        """Filter a queryset to only show items from user's institution"""
        institution = MultiTenantService.get_user_institution(user)
        
        if not institution:
            # User doesn't belong to an institution
            # Show only public/shared content
            return base_queryset.filter(institution__isnull=True)
        
        # Check if user is an admin
        if MultiTenantService.is_institution_admin(user, institution):
            # Admin sees all content from their institution
            return base_queryset.filter(institution=institution)
        
        # Regular user sees only content from their institution
        return base_queryset.filter(institution=institution)
    
    @staticmethod
    def create_invitation(institution, email, role, department=None, invited_by=None):
        """Create an invitation to join an institution"""
        token = secrets.token_urlsafe(32)
        expires = timezone.now() + timedelta(days=7)
        
        invitation = InstitutionInvitation.objects.create(
            institution=institution,
            email=email,
            role=role,
            department=department,
            invited_by=invited_by,
            token=token,
            expires_at=expires
        )
        
        return invitation
    
    @staticmethod
    def accept_invitation(token):
        """Accept an invitation and add user to institution"""
        try:
            invitation = InstitutionInvitation.objects.get(token=token)
            
            if not invitation.is_valid():
                return None, "Invitation has expired or already been used"
            
            # Add user to institution (would need to update user model)
            # This is a placeholder - actual implementation would update user
            
            invitation.accepted = True
            invitation.accepted_at = timezone.now()
            invitation.save()
            
            return invitation, None
        except InstitutionInvitation.DoesNotExist:
            return None, "Invalid invitation"
    
    @staticmethod
    def detect_institution_from_email(email) -> Institution | None:
        """Detect institution from email domain"""
        domain = email.split('@')[1] if '@' in email else ''
        
        if not domain:
            return None
        
        return Institution.objects.filter(
            email_domain__iendswith=domain,
            is_active=True,
            allow_registration=True
        ).first()
    
    @staticmethod
    def get_departments(institution) -> list[Department]:
        """Get all departments for an institution"""
        return Department.objects.filter(
            institution=institution,
            is_active=True
        ).order_by('name')
    
    @staticmethod
    def create_department(institution, name, code, head=None) -> Department:
        """Create a new department"""
        return Department.objects.create(
            institution=institution,
            name=name,
            code=code,
            head=head
        )


class InstitutionStatisticsService:
    """Service for institution statistics"""
    
    @staticmethod
    def get_institution_stats(institution) -> dict:
        """Get statistics for an institution"""
        
        # User counts
        total_users = institution.users.count()
        
        # Get department breakdown
        departments = Department.objects.filter(
            institution=institution,
            is_active=True
        ).annotate(
            user_count=models.Count('users')
        )
        
        # Activity stats (placeholder - would need actual tracking)
        return {
            'total_users': total_users,
            'active_users': total_users,  # Would filter by last_login
            'departments': departments.count(),
            'storage_used_gb': 0,  # Would calculate from actual storage
            'subscription_tier': institution.subscription_tier,
            'subscription_active': institution.is_subscription_active,
        }
