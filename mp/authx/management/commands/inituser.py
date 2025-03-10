from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = "Seed initial user for local testing."

    def handle(self, *args, **options):
        if settings.APP_ENVIRONMENT != "local":
            self.stdout.write(
                self.style.ERROR("Unable to set test user for non-local environment.")
            )
            return

        user, _ = User.objects.get_or_create(
            email=settings.TEST_USER_EMAIL,
            defaults={
                "protected_symmetric_key": settings.TEST_USER_PROTECTED_SYMMETRIC_KEY,
                "is_active": True,
                "verified": True,
            },
        )
        user.set_password(settings.TEST_USER_LOGIN_HASH)
        user.save(update_fields=["password"])
        self.stdout.write(self.style.SUCCESS("Test user %s is set." % user.email))
