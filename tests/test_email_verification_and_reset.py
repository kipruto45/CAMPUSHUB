import pytest
from django.core import mail
from django.urls import reverse
from django.contrib.auth import get_user_model


@pytest.mark.django_db
def test_signup_sends_verification_email(client, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.FRONTEND_BASE_URL = "https://example.com"

    payload = {
        "username": "newuser",
        "email": "new@example.com",
        "password1": "StrongPassw0rd!",
        "password2": "StrongPassw0rd!",
    }
    resp = client.post(reverse("accounts:register"), payload)
    assert resp.status_code in (200, 201, 302)

    assert len(mail.outbox) >= 1
    message = mail.outbox[0]
    html = message.alternatives[0][0]
    assert "https://example.com" in html
    assert "Verify" in html


@pytest.mark.django_db
def test_password_reset_sends_email(client, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.FRONTEND_BASE_URL = "https://example.com"

    User = get_user_model()
    user = User.objects.create_user(
        username="resetuser", email="reset@example.com", password="Passw0rd!"
    )

    resp = client.post(reverse("accounts:password_reset"), {"email": user.email})
    assert resp.status_code in (200, 302)
    assert len(mail.outbox) >= 1
    html = mail.outbox[0].alternatives[0][0]
    assert "https://example.com/password-reset" in html


@pytest.mark.django_db
def test_payment_success_email_includes_receipt_url(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.FRONTEND_BASE_URL = "https://example.com"

    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from apps.payments.models import Payment
    from apps.payments.notifications import PaymentNotificationService

    User = get_user_model()
    user = User.objects.create_user(username="payu", email="pay@example.com", password="Passw0rd!")
    payment = Payment.objects.create(
        user=user,
        amount=Decimal("5.00"),
        currency="USD",
        payment_type="subscription",
        status="succeeded",
    )

    assert PaymentNotificationService.send_payment_success_email(
        user=user,
        amount=Decimal("5.00"),
        currency="USD",
        payment_type="subscription",
        payment_id="TEST",
        payment=payment,
    )

    assert len(mail.outbox) >= 1
    html = mail.outbox[-1].alternatives[0][0]
    assert "Download Receipt" in html or "Receipt" in html
