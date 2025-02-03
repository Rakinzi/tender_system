from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
import uuid

def generate_verification_token():
    return str(uuid.uuid4())

def send_verification_email(user, token):
    subject = 'Verify your email address'
    current_time = timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')
    message = f"""
    Hello {user.first_name},

    Please verify your email address by clicking the link below:
    {settings.SITE_URL}/api/auth/verify-email/{token}/

    This link will expire in 24 hours.
    
    Email sent at: {current_time}

    If you didn't create this account, please ignore this email.

    Best regards,
    Your Application Team
    """
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )

def send_password_reset_email(user, token):
    subject = 'Reset your password'
    current_time = timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')
    message = f"""
    Hello {user.first_name},

    You've requested to reset your password. Click the link below to proceed:
    {settings.SITE_URL}/api/auth/reset-password/{token}/

    This link will expire in 1 hour.
    
    Request made at: {current_time}

    If you didn't request this password reset, please ignore this email.

    Best regards,
    Your Application Team
    """
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )