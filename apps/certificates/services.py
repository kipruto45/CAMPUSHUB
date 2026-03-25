"""
Services for certificate generation.
"""

import io
import os
from datetime import datetime

import qrcode
from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


class CertificatePDFService:
    """
    Service for generating PDF certificates.
    """

    def __init__(self, certificate):
        self.certificate = certificate
        self.template = certificate.template
        self.styles = getSampleStyleSheet()

    def generate_pdf(self):
        """Generate PDF certificate and return the file path."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72,
        )

        story = []
        story.extend(self._build_header())
        story.extend(self._build_body())
        story.extend(self._build_footer())

        doc.build(story)

        buffer.seek(0)
        return buffer

    def _build_header(self):
        """Build the header section of the certificate."""
        elements = []

        # Certificate title
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=self.styles["Heading1"],
            fontSize=36,
            textColor=colors.HexColor(self.template.text_color if self.template else "#000000"),
            spaceAfter=30,
            alignment=1,
        )
        title = Paragraph(self.certificate.title, title_style)
        elements.append(title)

        elements.append(Spacer(1, 20))
        return elements

    def _build_body(self):
        """Build the body section of the certificate."""
        elements = []

        # "This is to certify that"
        certify_style = ParagraphStyle(
            "Certify",
            parent=self.styles["Normal"],
            fontSize=14,
            textColor=colors.black,
            spaceAfter=20,
            alignment=1,
        )
        certify_text = Paragraph("This is to certify that", certify_style)
        elements.append(certify_text)

        # Recipient name
        name_style = ParagraphStyle(
            "RecipientName",
            parent=self.styles["Heading2"],
            fontSize=28,
            textColor=colors.HexColor("#1a5f7a"),
            spaceAfter=20,
            alignment=1,
        )
        name = Paragraph(self.certificate.recipient_name, name_style)
        elements.append(name)

        # "has successfully completed"
        completed_style = ParagraphStyle(
            "Completed",
            parent=self.styles["Normal"],
            fontSize=14,
            textColor=colors.black,
            spaceAfter=20,
            alignment=1,
        )
        completed_text = Paragraph("has successfully completed", completed_style)
        elements.append(completed_text)

        # Course/Achievement name
        course_style = ParagraphStyle(
            "CourseName",
            parent=self.styles["Heading3"],
            fontSize=20,
            textColor=colors.HexColor("#000000"),
            spaceAfter=30,
            alignment=1,
        )

        if self.certificate.course:
            course_text = self.certificate.course.name
        elif self.certificate.achievement:
            course_text = self.certificate.achievement.name
        else:
            course_text = self.certificate.description or "the required course"

        course = Paragraph(course_text, course_style)
        elements.append(course)

        elements.append(Spacer(1, 20))
        return elements

    def _build_footer(self):
        """Build the footer section of the certificate."""
        elements = []

        # Issue date
        date_style = ParagraphStyle(
            "Date",
            parent=self.styles["Normal"],
            fontSize=12,
            textColor=colors.black,
            spaceAfter=5,
            alignment=1,
        )
        issue_date = self.certificate.issue_date.strftime("%B %d, %Y")
        date_text = Paragraph(f"Issued on: {issue_date}", date_style)
        elements.append(date_text)

        # Issuing authority
        authority_style = ParagraphStyle(
            "Authority",
            parent=self.styles["Heading4"],
            fontSize=16,
            textColor=colors.black,
            spaceAfter=30,
            alignment=1,
        )
        authority = Paragraph(self.certificate.issuing_authority, authority_style)
        elements.append(authority)

        # Certificate ID and verification
        elements.append(Spacer(1, 20))

        # Create a table for certificate ID and QR code
        data = [
            [
                Paragraph(
                    f"<b>Certificate ID:</b> {self.certificate.unique_id}",
                    self.styles["Normal"],
                ),
                "",
            ],
            [
                Paragraph(
                    f"<b>Verification URL:</b><br/>{self.certificate.verification_url}",
                    self.styles["Normal"],
                ),
                "",
            ],
        ]

        table = Table(data, colWidths=[4 * inch, 3 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (0, -1), "LEFT"),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ]
            )
        )
        elements.append(table)

        return elements


class CertificateQRCodeService:
    """
    Service for generating QR codes for certificate verification.
    """

    def generate_qr_code(self, certificate):
        """Generate QR code for certificate verification."""
        qr_data = certificate.get_verification_data()

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        return buffer


class CertificateService:
    """
    Main service for certificate generation operations.
    """

    def __init__(self):
        self.pdf_service = CertificatePDFService
        self.qr_service = CertificateQRCodeService()

    def generate_certificate(self, certificate):
        """
        Generate PDF and QR code for a certificate.

        Args:
            certificate: Certificate instance

        Returns:
            Certificate with PDF and QR code generated
        """
        # Generate QR code
        qr_buffer = self.qr_service.generate_qr_code(certificate)
        qr_filename = f"qr_{certificate.unique_id}.png"
        certificate.qr_code.save(qr_filename, qr_buffer, save=True)

        # Generate PDF
        pdf_service = self.pdf_service(certificate)
        pdf_buffer = pdf_service.generate_pdf()
        pdf_filename = f"certificate_{certificate.unique_id}.pdf"
        certificate.pdf_file.save(pdf_filename, pdf_buffer, save=True)

        certificate.save()

        return certificate

    def verify_certificate(self, unique_id):
        """
        Verify a certificate by its unique ID.

        Args:
            unique_id: Certificate unique ID

        Returns:
            Certificate instance or None if not found
        """
        from apps.certificates.models import Certificate

        try:
            certificate = Certificate.objects.get(unique_id=unique_id)
            return {
                "valid": certificate.is_valid(),
                "certificate": certificate,
                "message": "Certificate is valid" if certificate.is_valid() else "Certificate is invalid or expired",
            }
        except Certificate.DoesNotExist:
            return {
                "valid": False,
                "certificate": None,
                "message": "Certificate not found",
            }

    def get_certificate_pdf(self, certificate):
        """
        Get the PDF file for a certificate.

        Args:
            certificate: Certificate instance

        Returns:
            File object or None
        """
        if certificate.pdf_file:
            return certificate.pdf_file.open()
        return None

    def create_course_completion_certificate(self, user, course, issued_by=None):
        """
        Create a course completion certificate.

        Args:
            user: User instance
            course: Course instance
            issued_by: User who issued the certificate (optional)

        Returns:
            Certificate instance
        """
        from apps.certificates.models import Certificate, CertificateType, CertificateTemplate

        # Get or create certificate type
        cert_type, _ = CertificateType.objects.get_or_create(
            slug="course-completion",
            defaults={
                "name": "Course Completion",
                "type": "course_completion",
                "description": "Certificate for completing a course",
            },
        )

        # Get default template
        template = CertificateTemplate.objects.filter(
            certificate_type=cert_type,
            is_default=True,
            is_active=True,
        ).first()

        # Create certificate
        certificate = Certificate.objects.create(
            user=user,
            certificate_type=cert_type,
            template=template,
            title=f"Certificate of Completion - {course.name}",
            recipient_name=user.get_full_name() or user.email,
            description=f"Successfully completed {course.name}",
            course=course,
            issuing_authority="CampusHub",
            issued_by=issued_by,
        )

        # Generate PDF and QR code
        self.generate_certificate(certificate)

        return certificate

    def create_achievement_certificate(self, user, achievement, issued_by=None):
        """
        Create an achievement certificate.

        Args:
            user: User instance
            achievement: Achievement instance
            issued_by: User who issued the certificate (optional)

        Returns:
            Certificate instance
        """
        from apps.certificates.models import Certificate, CertificateType, CertificateTemplate

        # Get or create certificate type
        cert_type, _ = CertificateType.objects.get_or_create(
            slug="achievement",
            defaults={
                "name": "Achievement",
                "type": "achievement",
                "description": "Certificate for achieving a milestone",
            },
        )

        # Get default template
        template = CertificateTemplate.objects.filter(
            certificate_type=cert_type,
            is_default=True,
            is_active=True,
        ).first()

        # Create certificate
        certificate = Certificate.objects.create(
            user=user,
            certificate_type=cert_type,
            template=template,
            title=f"Achievement Certificate - {achievement.name}",
            recipient_name=user.get_full_name() or user.email,
            description=achievement.description or f"Achieved {achievement.name}",
            achievement=achievement,
            issuing_authority="CampusHub",
            issued_by=issued_by,
        )

        # Generate PDF and QR code
        self.generate_certificate(certificate)

        return certificate

    def create_custom_certificate(
        self,
        user,
        title,
        description,
        issuing_authority="CampusHub",
        issued_by=None,
        expiry_date=None,
    ):
        """
        Create a custom certificate.

        Args:
            user: User instance
            title: Certificate title
            description: Certificate description
            issuing_authority: Authority issuing the certificate
            issued_by: User who issued the certificate (optional)
            expiry_date: Expiry date (optional)

        Returns:
            Certificate instance
        """
        from apps.certificates.models import Certificate, CertificateType, CertificateTemplate

        # Get or create certificate type
        cert_type, _ = CertificateType.objects.get_or_create(
            slug="custom",
            defaults={
                "name": "Custom Certificate",
                "type": "custom",
                "description": "Custom certificate",
            },
        )

        # Get default template
        template = CertificateTemplate.objects.filter(
            certificate_type=cert_type,
            is_default=True,
            is_active=True,
        ).first()

        # Create certificate
        certificate = Certificate.objects.create(
            user=user,
            certificate_type=cert_type,
            template=template,
            title=title,
            recipient_name=user.get_full_name() or user.email,
            description=description,
            issuing_authority=issuing_authority,
            issued_by=issued_by,
            expiry_date=expiry_date,
        )

        # Generate PDF and QR code
        self.generate_certificate(certificate)

        return certificate
