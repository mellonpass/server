import strawberry

from mp.cipher.graphql.mutations import CipherMutation
from mp.cipher.graphql.queries import CipherQuery


@strawberry.type
class Mutation:
    @strawberry.field
    def cipher(self) -> CipherMutation:
        return CipherMutation()


@strawberry.type
class Query(CipherQuery): ...
