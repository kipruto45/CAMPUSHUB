"""
Management command to create a sample institution for testing.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.institutions.models import Institution, InstitutionAdmin, Department


class Command(BaseCommand):
    help = "Create sample institution for testing"

    def handle(self, *args, **options):
        User = get_user_model()
        
        # Check if institution already exists
        if Institution.objects.filter(slug="sample-university").exists():
            self.stdout.write("Sample institution already exists!")
            return
        
        # Create institution
        institution = Institution.objects.create(
            name="Sample University",
            short_name="Sample Uni",
            slug="sample-university",
            description="A sample university for testing CampusHub",
            email_domain="@sample.edu",
            website="https://sample.edu",
            phone="+1234567890",
            address="123 University Ave, City, Country",
            institution_type="university",
            is_active=True,
            is_verified=True,
            allow_registration=True,
            subscription_tier="free",
            primary_color="#007bff",
            secondary_color="#6c757d",
        )
        
        self.stdout.write(f"Created institution: {institution.name}")
        
        # Create admin user if not exists
        admin_email = "admin@sample.edu"
        admin_user, created = User.objects.get_or_create(
            email=admin_email,
            defaults={
                "full_name": "Admin User",
                "role": "admin",
            }
        )
        if created:
            admin_user.set_password("admin123")
            admin_user.save()
            self.stdout.write(f"Created admin user: {admin_email} (password: admin123)")
        else:
            self.stdout.write(f"Admin user already exists: {admin_email}")
        
        # Create InstitutionAdmin role
        InstitutionAdmin.objects.get_or_create(
            user=admin_user,
            institution=institution,
            defaults={
                "role": "owner",
                "can_manage_users": True,
                "can_manage_content": True,
                "can_manage_settings": True,
                "can_view_analytics": True,
                "is_active": True,
            }
        )
        
        # Create sample departments
        departments = [
            {"name": "Computer Science", "code": "CS"},
            {"name": "Business Administration", "code": "BA"},
            {"name": "Engineering", "code": "ENG"},
            {"name": "Arts and Humanities", "code": "AH"},
        ]
        
        for dept_data in departments:
            Department.objects.get_or_create(
                institution=institution,
                code=dept_data["code"],
                defaults={"name": dept_data["name"]}
            )
        
        self.stdout.write(self.style.SUCCESS(f"✓ Sample institution created successfully!"))
        self.stdout.write(f"  Institution: {institution.name}")
        self.stdout.write(f"  Admin Login: {admin_email} / admin123")
        self.stdout.write(f"  Website: https://my-cham-a.app (after deployment)")