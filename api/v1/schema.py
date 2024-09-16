import strawberry

from apps.authx.api.v1 import schema as account_schema


@strawberry.type
class Mutation(account_schema.Mutation):
    pass


@strawberry.type
class Query:
    @strawberry.field
    def version(self) -> str:
        return "v1"


schema = strawberry.Schema(query=Query, mutation=Mutation)
