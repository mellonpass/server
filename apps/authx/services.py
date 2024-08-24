from apps.authx.models import User


def create_user(email: str, name: str, login_hash: str) -> User:
    return User.objects.create_user(email=email, password=login_hash, name=name)
