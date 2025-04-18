import strawberry
from django.conf import settings
from graphql.validation import NoSchemaIntrospectionCustomRule
from strawberry.extensions import AddValidationRules, QueryDepthLimiter
from strawberry.tools import merge_types

from mp.apps.cipher.graphql import schema as cipher_schema


def _get_extensions():
    ext = []

    if not settings.DEBUG:
        ext = [
            AddValidationRules([NoSchemaIntrospectionCustomRule]),
            QueryDepthLimiter(max_depth=5),
        ]

    return ext


Mutation = merge_types(
    "Mutation",
    (cipher_schema.Mutation,),
)

Query = merge_types("Query", (cipher_schema.CipherQuery,))

schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    extensions=_get_extensions(),
)
