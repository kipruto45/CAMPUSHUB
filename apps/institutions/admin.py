"""
Admin configuration for Institutions
"""

from django.contrib import admin
from .models import Institution, InstitutionAdmin as InstitutionAdminModel, Department, InstitutionInvitation


@admin.register(Institution)
class InstitutionModelAdmin(admin.ModelAdmin):
    list_display = ['name', 'short_name', 'institution_type', 'is_active', 'is_verified', 'subscription_tier']
    list_filter = ['institution_type', 'is_active', 'is_verified', 'subscription_tier']
    search_fields = ['name', 'short_name', 'email_domain']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(InstitutionAdminModel)
class InstitutionAdminRoleAdmin(admin.ModelAdmin):
    list_display = ['user', 'institution', 'role', 'is_active']
    list_filter = ['role', 'is_active']
    search_fields = ['user__email', 'institution__name']
    raw_id_fields = ['user', 'institution']


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'institution', 'is_active']
    list_filter = ['institution', 'is_active']
    search_fields = ['name', 'code']
    raw_id_fields = ['institution', 'head']


@admin.register(InstitutionInvitation)
class InstitutionInvitationAdmin(admin.ModelAdmin):
    list_display = ['email', 'institution', 'role', 'accepted', 'expires_at']
    list_filter = ['accepted', 'role']
    search_fields = ['email', 'institution__name']
    raw_id_fields = ['institution', 'invited_by', 'department']
