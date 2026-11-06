from uuid import uuid4

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from mp.core.model.fields import EncryptedTextField


class Organization(models.Model):
    uuid = models.UUIDField(unique=True, default=uuid4, editable=False)
    name = models.CharField(max_length=150)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name


class OrganizationMemberRole(models.TextChoices):
    OWNER = "OWNER", _("Owner")
    ADMIN = "ADMIN", _("Admin")
    MEMBER = "MEMBER", _("Member")


class OrganizationMemberStatus(models.TextChoices):
    INVITED = "INVITED", _("Invited")
    ACCEPTED = "ACCEPTED", _("Accepted")
    CONFIRMED = "CONFIRMED", _("Confirmed")
    REVOKED = "REVOKED", _("Revoked")


class OrganizationMember(models.Model):
    uuid = models.UUIDField(unique=True, default=uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        related_name="members",
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="organization_memberships",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    email = models.EmailField(help_text="Target email for invitation")
    role = models.CharField(
        max_length=20,
        choices=OrganizationMemberRole.choices,
        default=OrganizationMemberRole.MEMBER,
    )
    status = models.CharField(
        max_length=20,
        choices=OrganizationMemberStatus.choices,
        default=OrganizationMemberStatus.INVITED,
    )
    invite_token = models.CharField(
        max_length=128,
        null=True,
        blank=True,
        unique=True,
    )
    protected_symmetric_key = EncryptedTextField(
        null=True,
        blank=True,
        help_text=(
            "Protected organization symmetric key encrypted with member's "
            "RSA public key."
        ),
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("organization", "email")

    def __str__(self) -> str:
        return f"{self.organization.name} - {self.email} ({self.role})"
