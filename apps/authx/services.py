from apps.authx.models import User, UserSymmetricKey
from typing import Optional


def create_account(
    email: str,
    name: str,
    login_hash: str,
    protected_symmetric_key: str,
    hint: Optional[str] = None,
) -> User:
    user = User.objects.create_user(
        email=email, password=login_hash, name=name, hint=hint
    )

    UserSymmetricKey.objects.create(user=user, pskey=protected_symmetric_key)
    return user
