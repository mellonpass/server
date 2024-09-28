from django.conf import settings
from marshmallow import Schema, fields, validate


class AccountCreateSerializer(Schema):
    uuid = fields.UUID(dump_only=True)
    email = fields.Email(required=True)
    name = fields.Str(required=True, validate=validate.Length(min=8))
    login_hash = fields.Str(required=True, load_only=True)
    protected_symmetric_key = fields.Str(required=True, load_only=True)
    hint = fields.Str(required=True, load_only=True)
    success_redirect_url = fields.Str(
        dump_only=True, dump_default=settings.ACCOUNT_CREATE_SUCCESS_REDIRECT_URL
    )


class AuthenticationSerializer(Schema):
    email = fields.Email(required=True, load_only=True)
    login_hash = fields.Str(required=True, load_only=True)
