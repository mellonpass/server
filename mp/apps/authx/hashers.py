from django.contrib.auth.hashers import Argon2PasswordHasher, PBKDF2PasswordHasher


class MellonPassPBKDF2PasswordHasher(PBKDF2PasswordHasher):
    """A subclass of PBKDF2PasswordHasher that uses 720k iterations."""

    iterations = 720000


class MellonPassArgon2PasswordHasher(Argon2PasswordHasher):
    """A subclass of Argon2PasswordHasher that uses 10x time cost."""

    time_cost = 10
