from marshmallow import Schema, fields, validate


class AccountCreateSerializer(Schema):
    email = fields.Email(required=True)
    name = fields.Str(required=True, validate=validate.Length(min=8))


class AuthenticationSerializer(Schema):
    email = fields.Email(required=True, load_only=True)
    login_hash = fields.Str(required=True, load_only=True)


class RefreshTokenSerializer(Schema):
    token = fields.Str(required=True, load_only=True)
