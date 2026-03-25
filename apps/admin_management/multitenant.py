"""
Multi-tenant Admin Views
Provides role-based admin views for different organization levels
"""

from typing import Dict, List, Optional
from django.db.models import QuerySet
from django.contrib.auth import get_user_model


class AdminRole:
    """Admin role types for multi-tenancy."""
    SUPER_ADMIN = "super_admin"
    INSTITUTION_ADMIN = "institution_admin"
    FACULTY_ADMIN = "faculty_admin"
    DEPARTMENT_ADMIN = "department_admin"
    MODERATOR = "moderator"

    CHOICES = [
        (SUPER_ADMIN, "Super Admin"),
        (INSTITUTION_ADMIN, "Institution Admin"),
        (FACULTY_ADMIN, "Faculty Admin"),
        (DEPARTMENT_ADMIN, "Department Admin"),
        (MODERATOR, "Moderator"),
    ]


class MultiTenantAdminService:
    """
    Service for multi-tenant admin views and permissions.
    Allows different admin roles to see only their scope of data.
    """

    @staticmethod
    def get_admin_role(user) -> str:
        """Determine the admin role for a user."""
        if user.is_superuser:
            return AdminRole.SUPER_ADMIN
        
        # Check for custom role field
        if hasattr(user, 'admin_role'):
            return user.admin_role
        
        # Default to moderator for staff users
        if user.is_staff:
            return AdminRole.MODERATOR
        
        return "user"

    @staticmethod
    def filter_by_admin_scope(user, queryset: QuerySet) -> QuerySet:
        """
        Filter a queryset based on the admin's scope.
        
        Args:
            user: Admin user
            queryset: QuerySet to filter
            
        Returns:
            Filtered QuerySet based on admin role
        """
        role = MultiTenantAdminService.get_admin_role(user)
        
        if role == AdminRole.SUPER_ADMIN:
            # Super admins see everything
            return queryset
        
        if role == AdminRole.INSTITUTION_ADMIN:
            # Institution admins see their institution
            if hasattr(user, 'institution'):
                return queryset.filter(institution=user.institution)
            return queryset
        
        if role == AdminRole.FACULTY_ADMIN:
            # Faculty admins see their faculty
            if hasattr(user, 'faculty'):
                return queryset.filter(faculty=user.faculty)
            return queryset
        
        if role == AdminRole.DEPARTMENT_ADMIN:
            # Department admins see their department
            if hasattr(user, 'department'):
                return queryset.filter(department=user.department)
            return queryset
        
        # Moderators see only pending items
        return queryset.filter(moderation_status='pending')

    @staticmethod
    def get_admin_scope_info(user) -> Dict:
        """
        Get information about the admin's scope.
        
        Returns:
            Dictionary with scope details
        """
        role = MultiTenantAdminService.get_admin_role(user)
        
        scope = {
            'role': role,
            'can_manage_users': role in [AdminRole.SUPER_ADMIN, AdminRole.INSTITUTION_ADMIN],
            'can_manage_content': role in [AdminRole.SUPER_ADMIN, AdminRole.INSTITUTION_ADMIN, AdminRole.FACULTY_ADMIN, AdminRole.DEPARTMENT_ADMIN],
            'can_moderate': True,
            'can_view_analytics': role in [AdminRole.SUPER_ADMIN, AdminRole.INSTITUTION_ADMIN, AdminRole.FACULTY_ADMIN],
            'can_export': role in [AdminRole.SUPER_ADMIN, AdminRole.INSTITUTION_ADMIN],
            'can_manage_referrals': role in [AdminRole.SUPER_ADMIN, AdminRole.INSTITUTION_ADMIN],
            'can_manage_payments': role in [AdminRole.SUPER_ADMIN, AdminRole.INSTITUTION_ADMIN],
        }
        
        # Add scope-specific info
        if role == AdminRole.INSTITUTION_ADMIN and hasattr(user, 'institution'):
            scope['institution'] = str(user.institution)
        
        if role == AdminRole.FACULTY_ADMIN and hasattr(user, 'faculty'):
            scope['faculty'] = str(user.faculty)
        
        if role == AdminRole.DEPARTMENT_ADMIN and hasattr(user, 'department'):
            scope['department'] = str(user.department)
        
        return scope

    @staticmethod
    def get_accessible_resources(user, resource_queryset):
        """Get resources accessible to this admin."""
        return MultiTenantAdminService.filter_by_admin_scope(user, resource_queryset)

    @staticmethod
    def get_accessible_users(user, user_queryset):
        """Get users accessible to this admin."""
        role = MultiTenantAdminService.get_admin_role(user)
        
        if role == AdminRole.SUPER_ADMIN:
            return user_queryset
        
        if role == AdminRole.INSTITUTION_ADMIN:
            if hasattr(user, 'institution'):
                return user_queryset.filter(institution=user.institution)
        
        if role == AdminRole.FACULTY_ADMIN:
            if hasattr(user, 'faculty'):
                return user_queryset.filter(faculty=user.faculty)
        
        if role == AdminRole.DEPARTMENT_ADMIN:
            if hasattr(user, 'department'):
                return user_queryset.filter(department=user.department)
        
        # Moderators can't manage users
        return user_queryset.none()

    @staticmethod
    def can_access_admin_feature(user, feature: str) -> bool:
        """
        Check if admin can access a specific feature.
        
        Args:
            user: Admin user
            feature: Feature identifier
            
        Returns:
            True if allowed
        """
        role = MultiTenantAdminService.get_admin_role(user)
        
        feature_permissions = {
            'manage_users': [AdminRole.SUPER_ADMIN, AdminRole.INSTITUTION_ADMIN],
            'manage_faculties': [AdminRole.SUPER_ADMIN, AdminRole.INSTITUTION_ADMIN],
            'manage_departments': [AdminRole.SUPER_ADMIN, AdminRole.INSTITUTION_ADMIN, AdminRole.FACULTY_ADMIN],
            'moderate_content': [AdminRole.SUPER_ADMIN, AdminRole.INSTITUTION_ADMIN, AdminRole.FACULTY_ADMIN, AdminRole.DEPARTMENT_ADMIN, AdminRole.MODERATOR],
            'view_analytics': [AdminRole.SUPER_ADMIN, AdminRole.INSTITUTION_ADMIN, AdminRole.FACULTY_ADMIN],
            'export_data': [AdminRole.SUPER_ADMIN, AdminRole.INSTITUTION_ADMIN],
            'system_settings': [AdminRole.SUPER_ADMIN],
            'manage_billing': [AdminRole.SUPER_ADMIN, AdminRole.INSTITUTION_ADMIN],
            'manage_referrals': [AdminRole.SUPER_ADMIN, AdminRole.INSTITUTION_ADMIN],
            'manage_payments': [AdminRole.SUPER_ADMIN, AdminRole.INSTITUTION_ADMIN],
        }
        
        allowed_roles = feature_permissions.get(feature, [])
        return role in allowed_roles

    @staticmethod
    def get_navigation_menu(user) -> List[Dict]:
        """
        Get navigation menu based on admin role.
        
        Returns:
            List of menu items with permissions
        """
        role = MultiTenantAdminService.get_admin_role(user)
        
        base_menu = [
            {
                'id': 'dashboard',
                'label': 'Dashboard',
                'icon': '📊',
                'path': '/admin/',
                'permission': 'view',
            },
            {
                'id': 'notifications',
                'label': 'Notifications',
                'icon': '🔔',
                'path': '/admin/notifications/',
                'permission': 'view',
            },
        ]
        
        # Add role-specific menu items
        if MultiTenantAdminService.can_access_admin_feature(user, 'moderate_content'):
            base_menu.append({
                'id': 'moderation',
                'label': 'Content Moderation',
                'icon': '✅',
                'path': '/admin/moderation/',
                'permission': 'moderate',
            })
        
        if MultiTenantAdminService.can_access_admin_feature(user, 'manage_users'):
            base_menu.append({
                'id': 'users',
                'label': 'User Management',
                'icon': '👥',
                'path': '/admin/users/',
                'permission': 'manage',
            })

        if MultiTenantAdminService.can_access_admin_feature(user, 'manage_referrals'):
            base_menu.append({
                'id': 'referrals',
                'label': 'Referral System',
                'icon': '🎯',
                'path': '/admin/referrals/',
                'permission': 'manage',
            })

        if MultiTenantAdminService.can_access_admin_feature(user, 'manage_payments'):
            base_menu.append({
                'id': 'payments',
                'label': 'Payments',
                'icon': '💳',
                'path': '/admin/payments/',
                'permission': 'manage',
            })
        
        if MultiTenantAdminService.can_access_admin_feature(user, 'manage_faculties'):
            base_menu.append({
                'id': 'faculties',
                'label': 'Faculties',
                'icon': '🏫',
                'path': '/admin/faculties/',
                'permission': 'manage',
            })
        
        if MultiTenantAdminService.can_access_admin_feature(user, 'view_analytics'):
            base_menu.extend([
                {
                    'id': 'analytics',
                    'label': 'Analytics',
                    'icon': '📈',
                    'path': '/admin/analytics/',
                    'permission': 'view',
                },
                {
                    'id': 'predictive',
                    'label': 'Predictive Analytics',
                    'icon': '🔮',
                    'path': '/admin/predictive/',
                    'permission': 'view',
                },
            ])
        
        if MultiTenantAdminService.can_access_admin_feature(user, 'export_data'):
            base_menu.append({
                'id': 'reports',
                'label': 'Reports & Export',
                'icon': '📋',
                'path': '/admin/reports/',
                'permission': 'export',
            })
        
        if MultiTenantAdminService.can_access_admin_feature(user, 'system_settings'):
            base_menu.append({
                'id': 'settings',
                'label': 'System Settings',
                'icon': '⚙️',
                'path': '/admin/settings/',
                'permission': 'manage',
            })
        
        return base_menu
