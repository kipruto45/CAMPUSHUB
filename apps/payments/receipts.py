"""
Payment receipt generation service for CampusHub.
Generates PDF receipts and secure download URLs.
"""

import logging
import io
import hashlib
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.core.signing import Signer
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)


class ReceiptGenerator:
    """
    Service for generating payment receipts.
    """

    @staticmethod
    def generate_receipt_pdf(payment) -> bytes:
        """
        Generate a PDF receipt for a payment.
        
        Args:
            payment: Payment model instance
            
        Returns:
            PDF file as bytes
        """
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib import colors

            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch)
            
            styles = getSampleStyleSheet()
            title_style = styles['Title']
            heading_style = styles['Heading2']
            normal_style = styles['Normal']
            
            # Custom styles
            subtitle_style = ParagraphStyle(
                'Subtitle',
                parent=styles['Normal'],
                fontSize=10,
                textColor=colors.gray,
            )
            
            elements = []
            
            # Header - Company Info
            elements.append(Paragraph("CAMPUSHUB", title_style))
            elements.append(Paragraph("Payment Receipt", getSampleStyleSheet()['Heading1']))
            elements.append(Spacer(1, 20))
            
            # Receipt Details
            receipt_number = f"REC-{payment.id}-{payment.created_at.strftime('%Y%m%d')}"
            elements.append(Paragraph(f"<b>Receipt #:</b> {receipt_number}", normal_style))
            elements.append(Paragraph(f"<b>Date:</b> {payment.created_at.strftime('%B %d, %Y at %H:%M')}", normal_style))
            elements.append(Spacer(1, 20))
            
            # Transaction Info
            elements.append(Paragraph("TRANSACTION DETAILS", heading_style))
            elements.append(Spacer(1, 10))
            
            data = [
                ["Field", "Value"],
                ["Transaction ID", str(payment.metadata.get('provider_payment_id') or payment.stripe_payment_intent_id or payment.metadata.get('payment_id', 'N/A'))],
                ["Payment Provider", payment.metadata.get('provider', 'Stripe').upper()],
                ["Status", payment.status.upper()],
            ]
            
            table = Table(data, colWidths=[2*inch, 3.5*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 20))
            
            # Payment Amount
            elements.append(Paragraph("PAYMENT SUMMARY", heading_style))
            elements.append(Spacer(1, 10))
            
            payment_type = payment.payment_type or payment.metadata.get('type', 'Payment')
            payment_desc = payment.metadata.get('description', f'{payment_type.replace("_", " ").title()}')
            
            summary_data = [
                ["Description", payment_desc],
                ["Amount", f"{payment.currency} {payment.amount}"],
                ["Subtotal", f"{payment.currency} {payment.amount}"],
                ["Tax", f"{payment.currency} 0.00"],
                ["Total", f"<b>{payment.currency} {payment.amount}</b>"],
            ]
            
            summary_table = Table(summary_data, colWidths=[3*inch, 2.5*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f0f0f0')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.gray),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            elements.append(summary_table)
            elements.append(Spacer(1, 20))
            
            # User Info
            if payment.user:
                elements.append(Paragraph("CUSTOMER INFORMATION", heading_style))
                elements.append(Spacer(1, 10))
                
                user_data = [
                    ["Name", f"{payment.user.first_name} {payment.user.last_name}"],
                    ["Email", payment.user.email],
                    ["Username", payment.user.username],
                ]
                
                if hasattr(payment.user, 'phone_number') and payment.user.phone_number:
                    user_data.append(["Phone", payment.user.phone_number])
                
                user_table = Table(user_data, colWidths=[2*inch, 3.5*inch])
                user_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.gray),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ]))
                elements.append(user_table)
            
            elements.append(Spacer(1, 40))
            
            # Footer
            base_url = getattr(settings, "BASE_URL", "https://campushub.com")
            elements.append(Paragraph(
                f"<i>This is a computer-generated receipt. For support, contact support@campushub.com</i>",
                subtitle_style
            ))
            elements.append(Paragraph(
                f"<i>Generated on {timezone.now().strftime('%Y-%m-%d %H:%M:%S')} UTC</i>",
                subtitle_style
            ))
            
            # Build PDF
            doc.build(elements)
            pdf_bytes = buffer.getvalue()
            buffer.close()
            
            return pdf_bytes
            
        except ImportError as e:
            logger.warning(f"reportlab not installed, using HTML receipt: {e}")
            return ReceiptGenerator.generate_receipt_html(payment).encode('utf-8')
        except Exception as e:
            logger.error(f"Receipt generation failed: {e}")
            # Fallback to HTML-based receipt
            return ReceiptGenerator.generate_receipt_html(payment).encode('utf-8')

    @staticmethod
    def generate_receipt_html(payment) -> str:
        """Generate HTML receipt as fallback."""
        base_url = getattr(settings, "BASE_URL", "https://campushub.com")
        
        return f"""
<!DOCTYPE html>
<html>
<head>
    <title>Payment Receipt - CampusHub</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #667eea; color: white; padding: 20px; text-align: center; }}
        .section {{ margin: 20px 0; }}
        .label {{ font-weight: bold; color: #666; }}
        table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f5f5f5; }}
        .total {{ font-size: 24px; font-weight: bold; color: #667eea; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>CAMPUSHUB</h1>
        <h2>Payment Receipt</h2>
    </div>
    
    <div class="section">
        <p><span class="label">Receipt #:</span> REC-{payment.id}-{payment.created_at.strftime('%Y%m%d')}</p>
        <p><span class="label">Date:</span> {payment.created_at.strftime('%B %d, %Y at %H:%M')}</p>
    </div>
    
    <div class="section">
        <h3>Transaction Details</h3>
        <table>
            <tr><td class="label">Transaction ID</td><td>{payment.metadata.get('provider_payment_id') or payment.stripe_payment_intent_id or payment.metadata.get('payment_id', 'N/A')}</td></tr>
            <tr><td class="label">Provider</td><td>{payment.metadata.get('provider', 'Stripe').upper()}</td></tr>
            <tr><td class="label">Status</td><td>{payment.status.upper()}</td></tr>
        </table>
    </div>
    
    <div class="section">
        <h3>Payment Summary</h3>
        <table>
            <tr><td>Description</td><td>{payment.metadata.get('description', payment.payment_type or 'Payment')}</td></tr>
            <tr><td>Amount</td><td>{payment.currency} {payment.amount}</td></tr>
            <tr><td class="label">Total</td><td class="total">{payment.currency} {payment.amount}</td></tr>
        </table>
    </div>
    
    <div class="section">
        <h3>Customer Information</h3>
        <p><span class="label">Name:</span> {payment.user.first_name} {payment.user.last_name}</p>
        <p><span class="label">Email:</span> {payment.user.email}</p>
    </div>
    
    <footer style="margin-top: 40px; color: #666; font-size: 12px;">
        <p>Generated on {timezone.now().isoformat()} UTC</p>
    </footer>
</body>
</html>
"""

    @staticmethod
    def create_signed_url(payment_id, user_id) -> str:
        """
        Create a secure, time-limited signed URL for receipt download.
        
        Args:
            payment_id: Payment ID
            user_id: User ID for authentication
            
        Returns:
            Signed URL with expiry token
        """
        base_url = getattr(settings, "BASE_URL", "https://campushub.com")
        
        # Create signed token
        signer = Signer()
        expiry = timezone.now() + timedelta(hours=24)  # 24 hour expiry
        
        data = f"{payment_id}:{user_id}:{expiry.timestamp()}"
        signature = signer.sign(data)
        
        # Generate URL
        url = f"{base_url}/api/v1/payments/receipt/{payment_id}/download/?sig={signature}"
        
        return url


class ReceiptDownloadView:
    """
    View for downloading payment receipts.
    Handles secure, authenticated download.
    """
    
    @staticmethod
    def get_receipt(request, payment_id):
        """
        Process receipt download request with authentication.
        
        Args:
            request: HTTP request
            payment_id: Payment ID
            
        Returns:
            PDF response or error
        """
        from django.http import HttpResponse, Http404
        from django.core.signing import BadSignature, SignatureExpired
        
        user = request.user
        if not user.is_authenticated:
            # Try to validate signature for link-based access
            signature = request.GET.get('sig', '')
            if not signature:
                return HttpResponse("Unauthorized", status=401)
            
            try:
                signer = Signer()
                data = signer.unsign(signature)
                parts = data.split(':')
                
                if len(parts) != 3:
                    return HttpResponse("Invalid signature", status=400)
                
                payment_id_sig, user_id_sig, expiry_ts = parts
                expiry = datetime.fromtimestamp(float(expiry_ts), tz=dt_timezone.utc)

                if timezone.now() > expiry:
                    return HttpResponse("Link expired", status=400)
                if str(payment_id_sig) != str(payment_id):
                    return HttpResponse("Invalid receipt link", status=400)
                    
                # Load user for signature-based access
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    user = User.objects.get(pk=user_id_sig)
                except User.DoesNotExist:
                    return HttpResponse("User not found", status=404)
                    
            except (BadSignature, SignatureExpired, ValueError) as e:
                return HttpResponse("Invalid or expired link", status=400)
        
        # Get payment
        from apps.payments.models import Payment
        
        try:
            payment = Payment.objects.select_related('user').get(pk=payment_id)
        except Payment.DoesNotExist:
            raise Http404("Payment not found")
        
        # Authorization check - user can only download their own receipts
        # Admin can download any receipt
        if payment.user != user and not user.is_staff:
            return HttpResponse("Unauthorized", status=403)
        
        # Generate receipt
        pdf_content = ReceiptGenerator.generate_receipt_pdf(payment)
        
        # Return PDF response
        response = HttpResponse(pdf_content, content_type='application/pdf')
        receipt_number = f"REC-{payment.id}-{payment.created_at.strftime('%Y%m%d')}"
        response['Content-Disposition'] = f'attachment; filename="{receipt_number}.pdf"'
        
        return response


# ============== Email Integration ==============

def attach_receipt_to_email(payment, email_message):
    """
    Attach PDF receipt to an email message.
    
    Args:
        payment: Payment model instance
        email_message: EmailMultiAlternatives instance
    """
    try:
        pdf_content = ReceiptGenerator.generate_receipt_pdf(payment)
        receipt_number = f"REC-{payment.id}-{payment.created_at.strftime('%Y%m%d')}"
        
        email_message.attach(
            filename=f"{receipt_number}.pdf",
            content=pdf_content,
            mimetype='application/pdf'
        )
        logger.info(f"Attached receipt {receipt_number} to email")
    except Exception as e:
        logger.error(f"Failed to attach receipt: {e}")


def get_receipt_url_for_sms(payment) -> str:
    """
    Get receipt download URL for SMS notification.
    
    Args:
        payment: Payment model instance
        
    Returns:
        Shortened/download URL
    """
    return ReceiptGenerator.create_signed_url(payment.id, payment.user.id)
