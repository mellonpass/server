from marshmallow import Schema, fields, validate


class AccountSerializer(Schema):
    uuid = fields.UUID(dump_only=True)
    email = fields.Email(required=True)
    name = fields.Str(required=True, validate=validate.Length(min=8))
    login_hash = fields.Str(required=True, load_only=True)
    protected_symmetric_key = fields.Str(required=True, load_only=True)
    hint = fields.Str(required=True, load_only=True)
