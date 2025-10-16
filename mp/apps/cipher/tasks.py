import logging

from django.db import transaction
from django.utils import timezone
from huey import crontab
from huey.contrib.djhuey import db_periodic_task

from mp.apps.cipher.models import Cipher

logger = logging.getLogger(__name__)


@db_periodic_task(crontab(minute="0", hour="0"))
def delete_ciphers_task():
    with transaction.atomic():
        qs = Cipher.objects.filter(delete_on__lte=timezone.now())
        for c in qs:
            c.data.delete()
            c.delete()
            logger.info("Cipher %s has been deleted.", c.uuid)
