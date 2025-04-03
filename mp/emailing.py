import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from mp.apps.authx.models import EmailVerificationToken
from mp.crypto import verify_jwt

logger = logging.getLogger(__name__)


def send_account_verification_link(app_origin: str, email: str):
    with transaction.atomic():
        User = get_user_model()
        user = User.objects.get(email=email)

        if user.is_active:
            logger.warning(
                "Something trying to resend verification link to active user's email %s",
                user.email,
            )
            return

        jwt_token = EmailVerificationToken.generate_token_id()
        _, payload = verify_jwt(jwt_token, verify=False)

        EmailVerificationToken.objects.create(
            token_id=payload["sub"],
            user=user,
            expiry=EmailVerificationToken.get_default_expiry_date(),
        )

        context = {"setup_link": f"{app_origin}/account-setup?token_id={jwt_token}"}

        html_content = render_to_string("emails/verification_email.html", context)
        # Remove html tags.
        text_content = strip_tags(html_content)

        email = EmailMultiAlternatives(
            subject="Verify your account",
            body=text_content,
            from_email=settings.NO_REPLY_EMAIL,
            to=[email],
        )

        email.attach_alternative(html_content, "text/html")
        email.send()
