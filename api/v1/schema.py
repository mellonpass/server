import strawberry

from apps.authx.api.mutations import UserMutation


@strawberry.type
class Mutation:
    @strawberry.field
    def user(self) -> UserMutation:
        return UserMutation()


@strawberry.type
class Query:
    @strawberry.field
    def version(self) -> str:
        return "v1"


schema = strawberry.Schema(query=Query, mutation=Mutation)
