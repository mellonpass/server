from apps.authx.models import User
from typing import Optional


def create_account(
    email: str, name: str, login_hash: str, hint: Optional[str] = None
) -> User:
    return User.objects.create_user(
        email=email, password=login_hash, name=name, hint=hint
    )
