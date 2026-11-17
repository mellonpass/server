import secrets
from uuid import UUID

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from mp.apps.authx.models import User
from mp.apps.cipher.models import Cipher
from mp.apps.organizations.models import (
    Organization,
    OrganizationMember,
    OrganizationMemberRole,
    OrganizationMemberStatus,
)
from mp.core.exceptions import ServiceValidationError

MAX_ORGANIZATION_NAME_LENGTH = 150

ADMIN_ROLES = (
    OrganizationMemberRole.OWNER,
    OrganizationMemberRole.ADMIN,
)


def is_org_admin_or_owner(user: User, organization: Organization) -> bool:
    """Check if the user is a confirmed owner or admin in the organization."""
    return OrganizationMember.objects.filter(
        organization=organization,
        user=user,
        role__in=ADMIN_ROLES,
        status=OrganizationMemberStatus.CONFIRMED,
    ).exists()


def get_confirmed_membership(
    user: User,
    organization: Organization,
) -> OrganizationMember:
    """Retrieve the confirmed membership record for a user in an organization."""
    try:
        return OrganizationMember.objects.get(
            organization=organization,
            user=user,
            status=OrganizationMemberStatus.CONFIRMED,
        )
    except OrganizationMember.DoesNotExist as err:
        err_msg = "User is not a confirmed member of this organization."
        raise ServiceValidationError(err_msg) from err


@transaction.atomic
def create_organization(
    owner: User,
    name: str,
    protected_symmetric_key: str,
) -> Organization:
    """Create a new organization and assign creator as confirmed OWNER."""
    cleaned_name = name.strip() if name else ""
    if not cleaned_name:
        err_msg = "Organization name cannot be empty."
        raise ServiceValidationError(err_msg)
    if len(cleaned_name) > MAX_ORGANIZATION_NAME_LENGTH:
        err_msg = (
            "Organization name cannot exceed "
            f"{MAX_ORGANIZATION_NAME_LENGTH} characters."
        )
        raise ServiceValidationError(err_msg)

    cleaned_key = protected_symmetric_key.strip() if protected_symmetric_key else ""
    if not cleaned_key:
        err_msg = "Protected symmetric key cannot be empty for organization creation."
        raise ServiceValidationError(err_msg)

    organization = Organization.objects.create(name=cleaned_name)

    OrganizationMember.objects.create(
        organization=organization,
        user=owner,
        email=owner.email,
        role=OrganizationMemberRole.OWNER,
        status=OrganizationMemberStatus.CONFIRMED,
        protected_symmetric_key=cleaned_key,
    )

    return organization


@transaction.atomic
def invite_user(
    inviter: User,
    organization_uuid: UUID,
    email: str,
    role: str = OrganizationMemberRole.MEMBER,
) -> OrganizationMember:
    """Invite a user by email to join an organization.

    Requires inviter to be a confirmed OWNER or ADMIN.
    """
    try:
        organization = Organization.objects.get(uuid=organization_uuid)
    except Organization.DoesNotExist as err:
        err_msg = "Organization does not exist."
        raise ServiceValidationError(err_msg) from err

    if not is_org_admin_or_owner(inviter, organization):
        err_msg = "Only organization owners or admins can invite new members."
        raise ServiceValidationError(err_msg)

    if role not in OrganizationMemberRole.values:
        err_msg = f"Invalid member role '{role}'."
        raise ServiceValidationError(err_msg)

    inviter_membership = get_confirmed_membership(inviter, organization)
    if (
        inviter_membership.role == OrganizationMemberRole.ADMIN
        and role == OrganizationMemberRole.OWNER
    ):
        err_msg = "Admins cannot invite members with the OWNER role."
        raise ServiceValidationError(err_msg)

    cleaned_email = email.strip().lower() if email else ""
    if not cleaned_email:
        err_msg = "Invitation email cannot be empty."
        raise ServiceValidationError(err_msg)

    try:
        validate_email(cleaned_email)
    except ValidationError as err:
        err_msg = "Invalid email address format."
        raise ServiceValidationError(err_msg) from err

    existing_member = OrganizationMember.objects.filter(
        organization=organization,
        email=cleaned_email,
    ).first()

    invite_token = secrets.token_urlsafe(32)

    if existing_member:
        if existing_member.status in (
            OrganizationMemberStatus.INVITED,
            OrganizationMemberStatus.ACCEPTED,
            OrganizationMemberStatus.CONFIRMED,
        ):
            err_msg = (
                "A member with this email already exists or has a pending invitation."
            )
            raise ServiceValidationError(err_msg)

        # If existing record was REVOKED, re-issue a fresh invitation
        existing_member.status = OrganizationMemberStatus.INVITED
        existing_member.role = role
        existing_member.user = None
        existing_member.protected_symmetric_key = None
        existing_member.invite_token = invite_token
        existing_member.save()
        return existing_member

    return OrganizationMember.objects.create(
        organization=organization,
        email=cleaned_email,
        role=role,
        status=OrganizationMemberStatus.INVITED,
        invite_token=invite_token,
    )


@transaction.atomic
def accept_invite(
    user: User,
    invite_token: str,
) -> OrganizationMember:
    """Accept an organization invitation using an invite token.

    Transitions status from INVITED to ACCEPTED.
    """
    cleaned_token = invite_token.strip() if invite_token else ""
    if not cleaned_token:
        err_msg = "Invitation token cannot be empty."
        raise ServiceValidationError(err_msg)

    member = (
        OrganizationMember.objects.select_for_update()
        .filter(
            invite_token=cleaned_token,
            status=OrganizationMemberStatus.INVITED,
        )
        .first()
    )

    if not member:
        err_msg = "Invalid or expired invitation token."
        raise ServiceValidationError(err_msg)

    if user.email.strip().lower() != member.email.lower():
        err_msg = "This invitation was sent to a different email address."
        raise ServiceValidationError(err_msg)

    already_linked = (
        OrganizationMember.objects.filter(
            organization=member.organization,
            user=user,
        )
        .exclude(pk=member.pk)
        .exists()
    )

    if already_linked:
        err_msg = "User is already a member of this organization."
        raise ServiceValidationError(err_msg)

    member.user = user
    member.status = OrganizationMemberStatus.ACCEPTED
    member.invite_token = None
    member.save()

    return member


@transaction.atomic
def confirm_member(
    confirmer: User,
    member_uuid: UUID,
    protected_symmetric_key: str,
    *,
    expected_key_version: int | None = None,
) -> OrganizationMember:
    """Confirm an accepted member by providing the organization symmetric key.

    Requires confirmer to be a confirmed OWNER or ADMIN.
    """
    cleaned_key = protected_symmetric_key.strip() if protected_symmetric_key else ""
    if not cleaned_key:
        err_msg = "Protected symmetric key cannot be empty for confirmation."
        raise ServiceValidationError(err_msg)

    try:
        target_ref = OrganizationMember.objects.values(
            "pk",
            "organization_id",
        ).get(uuid=member_uuid)
    except OrganizationMember.DoesNotExist as err:
        err_msg = "Organization member not found."
        raise ServiceValidationError(err_msg) from err

    # Lock organization first to serialize with concurrent key rotations
    organization = Organization.objects.select_for_update().get(
        pk=target_ref["organization_id"],
    )

    try:
        member = (
            OrganizationMember.objects.select_for_update(of=("self",))
            .select_related(
                "organization",
                "user",
                "user__asymmetric_key",
            )
            .get(pk=target_ref["pk"])
        )
    except OrganizationMember.DoesNotExist as err:
        err_msg = "Organization member not found."
        raise ServiceValidationError(err_msg) from err

    if not is_org_admin_or_owner(confirmer, organization):
        err_msg = "Only organization owners or admins can confirm members."
        raise ServiceValidationError(err_msg)

    confirmer_membership = get_confirmed_membership(confirmer, organization)
    if (
        confirmer_membership.role == OrganizationMemberRole.ADMIN
        and member.role == OrganizationMemberRole.OWNER
    ):
        err_msg = "Admins cannot confirm an organization owner."
        raise ServiceValidationError(err_msg)

    if member.status != OrganizationMemberStatus.ACCEPTED:
        err_msg = (
            f"Cannot confirm member with status '{member.status}'. "
            "Status must be ACCEPTED."
        )
        raise ServiceValidationError(err_msg)

    if not member.user:
        err_msg = "Member must have an associated user account before confirmation."
        raise ServiceValidationError(err_msg)

    if (
        expected_key_version is not None
        and expected_key_version != organization.key_version
    ):
        err_msg = "Organization key version mismatch. Please refresh and try again."
        raise ServiceValidationError(err_msg)

    member.protected_symmetric_key = cleaned_key
    member.status = OrganizationMemberStatus.CONFIRMED
    member.save()

    # Keep in-memory relation aligned with locked row (harmless; org is unmodified)
    member.organization = organization
    return member


def _validate_revoker_permissions(
    revoker: User,
    organization: Organization,
    member: OrganizationMember,
) -> None:
    """Verify revoker role, target status, and last-owner protection."""
    revoker_membership = get_confirmed_membership(revoker, organization)
    if revoker_membership.role not in ADMIN_ROLES:
        err_msg = "Only organization owners or admins can revoke members."
        raise ServiceValidationError(err_msg)

    if (
        revoker_membership.role == OrganizationMemberRole.ADMIN
        and member.role == OrganizationMemberRole.OWNER
    ):
        err_msg = "Admins cannot revoke an organization owner."
        raise ServiceValidationError(err_msg)

    if member.status == OrganizationMemberStatus.REVOKED:
        err_msg = "Member is already revoked."
        raise ServiceValidationError(err_msg)

    if (
        member.role == OrganizationMemberRole.OWNER
        and member.status == OrganizationMemberStatus.CONFIRMED
    ):
        confirmed_owners_count = OrganizationMember.objects.filter(
            organization=organization,
            role=OrganizationMemberRole.OWNER,
            status=OrganizationMemberStatus.CONFIRMED,
        ).count()
        if confirmed_owners_count <= 1:
            err_msg = "Cannot revoke the last owner of an organization."
            raise ServiceValidationError(err_msg)


def _validate_rotation_key_map(
    provided_keys: dict[UUID, str] | None,
    expected_uuids: set[UUID],
    *,
    entity_label: str,
) -> dict[UUID, str]:
    """Validate that rotation keys cover all expected UUIDs with non-empty strings."""
    if provided_keys is None:
        err_msg = f"Rotated {entity_label} keys must be provided."
        raise ServiceValidationError(err_msg)

    provided_uuids = set(provided_keys.keys())
    if provided_uuids != expected_uuids:
        missing_count = len(expected_uuids - provided_uuids)
        extra_count = len(provided_uuids - expected_uuids)
        err_msg = (
            f"Incomplete or invalid rotated {entity_label} keys "
            f"(missing={missing_count}, unexpected={extra_count})."
        )
        raise ServiceValidationError(err_msg)

    cleaned: dict[UUID, str] = {}
    for item_uuid, raw_key in provided_keys.items():
        cleaned_key = raw_key.strip() if raw_key else ""
        if not cleaned_key:
            err_msg = f"Rotated {entity_label} key cannot be empty."
            raise ServiceValidationError(err_msg)
        cleaned[item_uuid] = cleaned_key
    return cleaned


@transaction.atomic
def revoke_member(
    revoker: User,
    member_uuid: UUID,
    *,
    expected_key_version: int | None = None,
    member_keys: dict[UUID, str] | None = None,
    cipher_keys: dict[UUID, str] | None = None,
) -> OrganizationMember:
    """Revoke a member's access and atomically rotate organization keys.

    Requires revoker to be a confirmed OWNER or ADMIN and supplies re-wrapped
    organization symmetric keys for remaining confirmed members and re-wrapped
    cipher keys for all organization ciphers.
    """
    try:
        target_ref = OrganizationMember.objects.values(
            "pk",
            "organization_id",
        ).get(uuid=member_uuid)
    except OrganizationMember.DoesNotExist as err:
        err_msg = "Organization member not found."
        raise ServiceValidationError(err_msg) from err

    # Lock organization first to serialize concurrent revocations & key rotations
    organization = Organization.objects.select_for_update().get(
        pk=target_ref["organization_id"],
    )

    try:
        member = (
            OrganizationMember.objects.select_for_update(of=("self",))
            .select_related(
                "organization",
                "user",
                "user__asymmetric_key",
            )
            .get(pk=target_ref["pk"])
        )
    except OrganizationMember.DoesNotExist as err:
        err_msg = "Organization member not found."
        raise ServiceValidationError(err_msg) from err

    _validate_revoker_permissions(revoker, organization, member)

    if expected_key_version is None:
        err_msg = "Expected organization key version must be provided."
        raise ServiceValidationError(err_msg)

    if expected_key_version != organization.key_version:
        err_msg = "Organization key version mismatch. Please refresh and try again."
        raise ServiceValidationError(err_msg)

    remaining_confirmed = list(
        OrganizationMember.objects.only("pk", "uuid")
        .select_for_update()
        .filter(
            organization=organization,
            status=OrganizationMemberStatus.CONFIRMED,
        )
        .exclude(pk=member.pk)
        .order_by("pk"),
    )
    org_ciphers = list(
        Cipher.objects.only("pk", "uuid")
        .select_for_update()
        .filter(organization=organization)
        .order_by("pk"),
    )

    cleaned_member_keys = _validate_rotation_key_map(
        member_keys,
        {m.uuid for m in remaining_confirmed},
        entity_label="member",
    )
    effective_cipher_keys = (
        cipher_keys if cipher_keys is not None else ({} if not org_ciphers else None)
    )
    cleaned_cipher_keys = _validate_rotation_key_map(
        effective_cipher_keys,
        {c.uuid for c in org_ciphers},
        entity_label="cipher",
    )

    now = timezone.now()
    if remaining_confirmed:
        for remaining_member in remaining_confirmed:
            remaining_member.protected_symmetric_key = cleaned_member_keys[
                remaining_member.uuid
            ]
            remaining_member.updated = now
        member_update_fields = ("protected_symmetric_key", "updated")
        OrganizationMember.objects.bulk_update(
            remaining_confirmed,
            member_update_fields,
            batch_size=500,
        )

    if org_ciphers:
        for cipher in org_ciphers:
            cipher.key = cleaned_cipher_keys[cipher.uuid]
            cipher.updated = now
        cipher_update_fields = ("key", "updated")
        Cipher.objects.bulk_update(
            org_ciphers,
            cipher_update_fields,
            batch_size=500,
        )

    member.status = OrganizationMemberStatus.REVOKED
    member.invite_token = None
    member.protected_symmetric_key = None
    member.save()

    organization.key_version += 1
    organization.save(update_fields=["key_version", "updated"])

    member.organization = organization
    return member


def get_user_organizations(user: User) -> QuerySet[Organization]:
    """Return all organizations where user has a CONFIRMED membership."""
    return Organization.objects.filter(
        members__user=user,
        members__status=OrganizationMemberStatus.CONFIRMED,
    ).distinct()


def get_organization_by_user_and_uuid(
    user: User,
    organization_uuid: UUID,
) -> Organization:
    """Return the organization if the user is a CONFIRMED member."""
    try:
        return Organization.objects.get(
            uuid=organization_uuid,
            members__user=user,
            members__status=OrganizationMemberStatus.CONFIRMED,
        )
    except Organization.DoesNotExist as err:
        err_msg = "Organization does not exist."
        raise ServiceValidationError(err_msg) from err


def get_pending_members(
    requester: User,
    organization_uuid: UUID,
) -> QuerySet[OrganizationMember]:
    """Return members with status ACCEPTED awaiting confirmation.

    Accessible only to confirmed owners or admins of the organization.
    """
    try:
        organization = Organization.objects.get(uuid=organization_uuid)
    except Organization.DoesNotExist as err:
        err_msg = "Organization does not exist."
        raise ServiceValidationError(err_msg) from err

    if not is_org_admin_or_owner(requester, organization):
        err_msg = "Only organization owners or admins can view pending members."
        raise ServiceValidationError(err_msg)

    return (
        OrganizationMember.objects.filter(
            organization=organization,
            status=OrganizationMemberStatus.ACCEPTED,
        )
        .select_related("user", "user__asymmetric_key")
        .order_by("created")
    )


def get_organization_members(
    requester: User,
    organization_uuid: UUID,
) -> QuerySet[OrganizationMember]:
    """Return all non-revoked members of an organization.

    Accessible to any confirmed member of the organization.
    """
    try:
        organization = Organization.objects.get(uuid=organization_uuid)
    except Organization.DoesNotExist as err:
        err_msg = "Organization does not exist."
        raise ServiceValidationError(err_msg) from err

    get_confirmed_membership(requester, organization)

    return (
        OrganizationMember.objects.filter(organization=organization)
        .exclude(status=OrganizationMemberStatus.REVOKED)
        .select_related("user", "user__asymmetric_key")
        .order_by("created")
    )
