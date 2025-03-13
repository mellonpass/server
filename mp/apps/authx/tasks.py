from huey.contrib.djhuey import on_commit_task

from mp.emailing import send_account_verification_link


@on_commit_task()
def send_account_verification_link_task(app_origin: str, email: str):
    send_account_verification_link(app_origin=app_origin, email=email)
