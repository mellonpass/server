import strawberry
from strawberry.tools import merge_types

from apps.cipher.api.v1 import schema as cipher_schema
from apps.jwt.api.v1 import schema as refresh_token_schema

Mutation = merge_types(
    "Mutation",
    (refresh_token_schema.Mutation, cipher_schema.Mutation),
)

Query = merge_types("Query", (cipher_schema.CipherQuery,))

schema = strawberry.Schema(query=Query, mutation=Mutation)
