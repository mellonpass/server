import strawberry

from apps.cipher.api.v1.mutations import CipherMutation
from apps.cipher.api.v1.queries import CipherQuery


@strawberry.type
class Mutation:
    @strawberry.field
    def Cipher(self) -> CipherMutation:
        return CipherMutation()


@strawberry.type
class Query(CipherQuery): ...
