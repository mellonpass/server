from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

from mp.authx.models import EmailVerificationToken


def send_account_verification_link(app_origin: str, email: str):
    User = get_user_model()
    user = User.objects.get(email=email)

    token_id = EmailVerificationToken.generate_token_id()

    EmailVerificationToken.objects.create(
        token_id=token_id,
        expiry=timezone.now() + timedelta(days=1),
        user=user,
    )

    context = {"setup_link": f"{app_origin}/account-setup?token_id={token_id}"}

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
