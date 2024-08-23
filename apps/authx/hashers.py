from django.contrib.auth.hashers import PBKDF2PasswordHasher


class MellonPassPBKDF2PasswordHasher(PBKDF2PasswordHasher):
    """A subclass of PBKDF2PasswordHasher that uses 720k iterations."""

    iterations = 720000
