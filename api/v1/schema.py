import strawberry

from apps.authx.api.mutations import AccountMutation


@strawberry.type
class Mutation:
    @strawberry.field
    def account(self) -> AccountMutation:
        return AccountMutation()


@strawberry.type
class Query:
    @strawberry.field
    def version(self) -> str:
        return "v1"


schema = strawberry.Schema(query=Query, mutation=Mutation)
