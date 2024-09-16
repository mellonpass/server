import strawberry

from apps.authx.api.v1.mutations import AccountMutation


@strawberry.type
class Mutation:
    @strawberry.field
    def Account(self) -> AccountMutation:
        return AccountMutation()
