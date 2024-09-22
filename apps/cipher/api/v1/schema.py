import strawberry

from apps.cipher.api.v1.mutations import CipherMutation


@strawberry.type
class Mutation:
    @strawberry.field
    def Cipher(self) -> CipherMutation:
        return CipherMutation()
