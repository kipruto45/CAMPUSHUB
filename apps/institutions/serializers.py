"""
Serializers for Institutions
"""

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_serializer
from .models import Institution, InstitutionAdmin, Department, InstitutionInvitation


class InstitutionSerializer(serializers.ModelSerializer):
    """Serializer for Institution"""
    user_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Institution
        fields = [
            'id', 'name', 'short_name', 'slug', 'description',
            'email_domain', 'website', 'phone', 'address',
            'logo', 'primary_color', 'secondary_color',
            'institution_type', 'is_active', 'is_verified',
            'require_email_verification', 'allow_registration',
            'max_users', 'max_storage_gb', 'max_file_size_mb',
            'subscription_tier', 'subscription_expires',
            'created_at', 'updated_at', 'user_count',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class InstitutionAdminSerializer(serializers.ModelSerializer):
    """Serializer for InstitutionAdmin"""
    user_email = serializers.CharField(source='user.email', read_only=True)
    institution_name = serializers.CharField(source='institution.name', read_only=True)
    
    class Meta:
        model = InstitutionAdmin
        fields = [
            'id', 'user', 'user_email', 'institution', 'institution_name',
            'role', 'can_manage_users', 'can_manage_content',
            'can_manage_settings', 'can_view_analytics',
            'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


@extend_schema_serializer(component_name="InstitutionDepartment")
class DepartmentSerializer(serializers.ModelSerializer):
    """Serializer for Department"""
    head_name = serializers.CharField(source='head.get_full_name', read_only=True)
    
    class Meta:
        model = Department
        fields = [
            'id', 'institution', 'name', 'code', 'description',
            'head', 'head_name', 'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class InstitutionInvitationSerializer(serializers.ModelSerializer):
    """Serializer for InstitutionInvitation"""
    invited_by_name = serializers.CharField(source='invited_by.get_full_name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    
    class Meta:
        model = InstitutionInvitation
        fields = [
            'id', 'institution', 'email', 'role', 'department',
            'department_name', 'invited_by', 'invited_by_name',
            'accepted', 'accepted_at', 'expires_at', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class InstitutionRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for institution registration (public)"""
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)
    contact_name = serializers.CharField(write_only=True, required=True)
    contact_email = serializers.EmailField(write_only=True, required=True)
    
    class Meta:
        model = Institution
        fields = [
            'name', 'short_name', 'slug', 'description',
            'email_domain', 'website', 'phone', 'address',
            'institution_type', 'password', 'confirm_password',
            'contact_name', 'contact_email',
        ]
    
    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match")
        return data
    
    def validate_slug(self, value):
        from django.utils.text import slugify
        slug = slugify(value)
        if Institution.objects.filter(slug=slug).exists():
            raise serializers.ValidationError("This URL slug is already taken")
        return slug


class InstitutionApprovalSerializer(serializers.ModelSerializer):
    """Serializer for institution approval"""
    
    class Meta:
        model = Institution
        fields = ['is_active', 'is_verified', 'subscription_tier']
