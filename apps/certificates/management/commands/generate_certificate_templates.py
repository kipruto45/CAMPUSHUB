"""
Management command to generate default certificate templates.
"""

from django.core.management.base import BaseCommand
from apps.certificates.models import CertificateType, CertificateTemplate


class Command(BaseCommand):
    help = "Generate default certificate templates"

    def handle(self, *args, **options):
        self.stdout.write("Creating certificate types...")

        # Create certificate types
        certificate_types = [
            {
                "name": "Course Completion",
                "slug": "course-completion",
                "type": "course_completion",
                "description": "Certificate awarded for completing a course",
            },
            {
                "name": "Achievement",
                "slug": "achievement",
                "type": "achievement",
                "description": "Certificate awarded for achieving a milestone",
            },
            {
                "name": "Milestone",
                "slug": "milestone",
                "type": "milestone",
                "description": "Certificate awarded for reaching a milestone",
            },
            {
                "name": "Custom",
                "slug": "custom",
                "type": "custom",
                "description": "Custom certificate template",
            },
        ]

        for type_data in certificate_types:
            cert_type, created = CertificateType.objects.get_or_create(
                slug=type_data["slug"],
                defaults=type_data,
            )
            if created:
                self.stdout.write(f"  Created: {cert_type.name}")
            else:
                self.stdout.write(f"  Exists: {cert_type.name}")

        self.stdout.write("\nCreating certificate templates...")

        # Get certificate types
        course_type = CertificateType.objects.get(slug="course-completion")
        achievement_type = CertificateType.objects.get(slug="achievement")
        milestone_type = CertificateType.objects.get(slug="milestone")
        custom_type = CertificateType.objects.get(slug="custom")

        # Create certificate templates
        templates = [
            {
                "name": "Classic Blue",
                "certificate_type": course_type,
                "title": "Certificate of Completion",
                "description": "This certificate is awarded to students who have successfully completed the course.",
                "background_color": "#FFFFFF",
                "border_color": "#1E3A5F",
                "text_color": "#1E3A5F",
                "footer_text": "CampusHub Learning Platform",
                "is_default": True,
                "is_active": True,
            },
            {
                "name": "Gold Achievement",
                "certificate_type": achievement_type,
                "title": "Achievement Certificate",
                "description": "This certificate recognizes outstanding achievement.",
                "background_color": "#FFFEF5",
                "border_color": "#D4AF37",
                "text_color": "#8B4513",
                "footer_text": "CampusHub - Recognizing Excellence",
                "is_default": True,
                "is_active": True,
            },
            {
                "name": "Milestone Purple",
                "certificate_type": milestone_type,
                "title": "Milestone Certificate",
                "description": "This certificate celebrates reaching a significant milestone.",
                "background_color": "#F5F3FF",
                "border_color": "#6B46C1",
                "text_color": "#553C9A",
                "footer_text": "CampusHub - Celebrating Success",
                "is_default": True,
                "is_active": True,
            },
            {
                "name": "Professional Green",
                "certificate_type": custom_type,
                "title": "Certificate of Achievement",
                "description": "This certificate recognizes exceptional accomplishment.",
                "background_color": "#F0FFF4",
                "border_color": "#276749",
                "text_color": "#22543D",
                "footer_text": "CampusHub - Empowering Learners",
                "is_default": True,
                "is_active": True,
            },
            {
                "name": "Modern Dark",
                "certificate_type": course_type,
                "title": "Certificate of Completion",
                "description": "Modern dark themed certificate for course completion.",
                "background_color": "#1A202C",
                "border_color": "#E53E3E",
                "text_color": "#E2E8F0",
                "footer_text": "CampusHub - Modern Learning",
                "is_default": False,
                "is_active": True,
            },
            {
                "name": "Elegant Gold",
                "certificate_type": achievement_type,
                "title": "Certificate of Excellence",
                "description": "Elegant gold themed certificate for excellence.",
                "background_color": "#FFFBEB",
                "border_color": "#B45309",
                "text_color": "#78350F",
                "footer_text": "CampusHub - Excellence in Learning",
                "is_default": False,
                "is_active": True,
            },
            {
                "name": "Fresh Mint",
                "certificate_type": milestone_type,
                "title": "Milestone Achievement",
                "description": "Fresh mint themed certificate for milestones.",
                "background_color": "#F0FDF4",
                "border_color": "#16A34A",
                "text_color": "#166534",
                "footer_text": "CampusHub - Growing Together",
                "is_default": False,
                "is_active": True,
            },
            {
                "name": "Royal Blue",
                "certificate_type": custom_type,
                "title": "Certificate",
                "description": "Royal blue themed certificate template.",
                "background_color": "#EFF6FF",
                "border_color": "#2563EB",
                "text_color": "#1E40AF",
                "footer_text": "CampusHub",
                "is_default": False,
                "is_active": True,
            },
        ]

        for template_data in templates:
            template, created = CertificateTemplate.objects.get_or_create(
                name=template_data["name"],
                certificate_type=template_data["certificate_type"],
                defaults=template_data,
            )
            if created:
                self.stdout.write(f"  Created: {template.name} ({template.certificate_type.name})")
            else:
                self.stdout.write(f"  Exists: {template.name} ({template.certificate_type.name})")

        # Count totals
        total_types = CertificateType.objects.count()
        total_templates = CertificateTemplate.objects.count()

        self.stdout.write(self.style.SUCCESS(f"\n✓ Successfully generated {total_types} certificate types and {total_templates} certificate templates"))