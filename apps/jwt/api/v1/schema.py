import strawberry

from apps.jwt.api.v1.mutations import RefreshTokenMutation


@strawberry.type
class Mutation:
    @strawberry.field
    def RefreshToken(self) -> RefreshTokenMutation:
        return RefreshTokenMutation()
