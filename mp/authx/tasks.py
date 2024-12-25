from celery import shared_task

from mp.emailing import send_account_verification_link


@shared_task
def send_account_verification_link_task(app_origin: str, email: str):
    send_account_verification_link(app_origin=app_origin, email=email)
