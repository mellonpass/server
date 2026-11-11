import secrets
from uuid import UUID

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import QuerySet

from mp.apps.authx.models import User
from mp.apps.organizations.models import (
    Organization,
    OrganizationMember,
    OrganizationMemberRole,
    OrganizationMemberStatus,
)
from mp.core.exceptions import ServiceValidationError

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

    member = OrganizationMember.objects.filter(
        invite_token=cleaned_token,
        status=OrganizationMemberStatus.INVITED,
    ).first()

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
            status__in=(
                OrganizationMemberStatus.ACCEPTED,
                OrganizationMemberStatus.CONFIRMED,
            ),
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
) -> OrganizationMember:
    """Confirm an accepted member by providing the organization symmetric key.

    Requires confirmer to be a confirmed OWNER or ADMIN.
    """
    cleaned_key = protected_symmetric_key.strip() if protected_symmetric_key else ""
    if not cleaned_key:
        err_msg = "Protected symmetric key cannot be empty for confirmation."
        raise ServiceValidationError(err_msg)

    try:
        member = OrganizationMember.objects.select_related(
            "organization",
            "user",
        ).get(uuid=member_uuid)
    except OrganizationMember.DoesNotExist as err:
        err_msg = "Organization member not found."
        raise ServiceValidationError(err_msg) from err

    if not is_org_admin_or_owner(confirmer, member.organization):
        err_msg = "Only organization owners or admins can confirm members."
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

    member.protected_symmetric_key = cleaned_key
    member.status = OrganizationMemberStatus.CONFIRMED
    member.save()

    return member


@transaction.atomic
def revoke_member(
    revoker: User,
    member_uuid: UUID,
) -> OrganizationMember:
    """Revoke a member's access to an organization (soft revocation).

    Requires revoker to be a confirmed OWNER or ADMIN.
    """
    try:
        member = OrganizationMember.objects.select_related(
            "organization",
            "user",
        ).get(uuid=member_uuid)
    except OrganizationMember.DoesNotExist as err:
        err_msg = "Organization member not found."
        raise ServiceValidationError(err_msg) from err

    revoker_membership = get_confirmed_membership(revoker, member.organization)
    if revoker_membership.role not in ADMIN_ROLES:
        err_msg = "Only organization owners or admins can revoke members."
        raise ServiceValidationError(err_msg)

    if (
        revoker_membership.role == OrganizationMemberRole.ADMIN
        and member.role == OrganizationMemberRole.OWNER
    ):
        err_msg = "Admins cannot revoke an organization owner."
        raise ServiceValidationError(err_msg)

    if (
        member.role == OrganizationMemberRole.OWNER
        and member.status == OrganizationMemberStatus.CONFIRMED
    ):
        confirmed_owners_count = OrganizationMember.objects.filter(
            organization=member.organization,
            role=OrganizationMemberRole.OWNER,
            status=OrganizationMemberStatus.CONFIRMED,
        ).count()
        if confirmed_owners_count <= 1:
            err_msg = "Cannot revoke the last owner of an organization."
            raise ServiceValidationError(err_msg)

    member.status = OrganizationMemberStatus.REVOKED
    member.invite_token = None
    member.save()

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
    return Organization.objects.get(
        uuid=organization_uuid,
        members__user=user,
        members__status=OrganizationMemberStatus.CONFIRMED,
    )


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
        .select_related("user")
        .order_by("created")
    )
