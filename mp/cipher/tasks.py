import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from mp.cipher.models import Cipher, CipherStatus

logger = logging.getLogger(__name__)


@shared_task
def delete_ciphers_task():
    with transaction.atomic():
        qs = Cipher.objects.filter(
            status=CipherStatus.DELETED, delete_on__lte=timezone.now()
        )
        for c in qs:
            c.delete()
            logger.info("Cipher %s has been deleted.", c.uuid)
