from celery import shared_task
from django.contrib.sessions.models import Session
from django.db.models import Q
from django.utils import timezone

from mp.jwt.models import RefreshToken


@shared_task
def revoke_inactive_refresh_tokens():
    """Inactive refresh tokens may be without session or expired."""
    expired_token_qs = RefreshToken.objects.filter(exp__lte=timezone.now())
    no_session_token_qs = RefreshToken.objects.exclude(
        session_key__in=list(Session.objects.values_list("session_key", flat=True))
    )

    # revoke expired tokens or token without sessions.
    (expired_token_qs | no_session_token_qs).update(
        revoked=True, datetime_revoked=timezone.now()
    )


@shared_task
def remove_revoked_refresh_tokens():
    RefreshToken.objects.filter(revoked=True).delete()
