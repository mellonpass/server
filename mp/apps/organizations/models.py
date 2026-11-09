from collections.abc import Iterable
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.db.models.base import ModelBase
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
        constraints = (
            models.UniqueConstraint(
                fields=["organization", "email"],
                name="unique_organization_email",
            ),
            models.UniqueConstraint(
                fields=["organization", "user"],
                condition=models.Q(user__isnull=False),
                name="unique_organization_user",
            ),
        )

    def __str__(self) -> str:
        return f"{self.organization.name} - {self.email} ({self.role})"

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if self.email:
            self.email = self.email.strip().lower()
        if self.invite_token is not None:
            self.invite_token = self.invite_token.strip() or None
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    def clean(self) -> None:
        super().clean()
        if self.email:
            self.email = self.email.strip().lower()
        if self.invite_token is not None:
            self.invite_token = self.invite_token.strip() or None
