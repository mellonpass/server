from collections.abc import Callable

from marshmallow import Schema, ValidationError, fields, validate


def _token_validator(max_length: int) -> Callable[[str], None]:
    """Build a Marshmallow validator for non-empty, whitespace-free token strings."""

    def _validate(value: str) -> None:
        if len(value) > max_length:
            err_msg = f"Longer than maximum length {max_length}."
            raise ValidationError(err_msg)
        if not value or not value.strip():
            err_msg = "Field must not be empty."
            raise ValidationError(err_msg)
        if any(ch.isspace() or not ch.isprintable() for ch in value):
            err_msg = "Field must not contain whitespace or control characters."
            raise ValidationError(err_msg)

    return _validate


class AccountCreateSerializer(Schema):
    email = fields.Email(required=True)
    name = fields.Str(required=True, validate=validate.Length(min=3))

    cf_turnstile_token = fields.Str(
        required=False,
        allow_none=True,
        load_only=True,
    )


class AuthenticationSerializer(Schema):
    email = fields.Email(required=True, load_only=True)
    login_hash = fields.Str(required=True, load_only=True)

    cf_turnstile_token = fields.Str(
        required=False,
        allow_none=True,
        load_only=True,
    )


class AccountSetupSerializer(Schema):
    email = fields.Email(required=True, load_only=True)
    protected_symmetric_key = fields.Str(required=True, load_only=True)
    login_hash = fields.Str(required=True, load_only=True)
    hint = fields.Str(validate=validate.Length(max=50), load_only=True)

    rsa_protected_private_key = fields.Str(required=True, load_only=True)
    rsa_public_key = fields.Str(required=True, load_only=True)


class ChangePasswordSerializer(Schema):
    current_login_hash = fields.Str(
        required=True,
        validate=_token_validator(1024),
        load_only=True,
    )
    new_login_hash = fields.Str(
        required=True,
        validate=_token_validator(1024),
        load_only=True,
    )
    new_protected_symmetric_key = fields.Str(
        required=True,
        validate=_token_validator(4096),
        load_only=True,
    )
    hint = fields.Str(
        required=False,
        allow_none=True,
        validate=validate.Length(max=50),
        load_only=True,
    )
