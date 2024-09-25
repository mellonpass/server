import strawberry

from apps.cipher.api.v1.types import (
    Cipher,
    CipherCreatePayload,
    CipherCreateSuccess,
    CreateCipherInput,
)
from apps.cipher.services import create_cipher
from apps.core.graphql.permissions import IsAuthenticated


@strawberry.type
class CipherMutation:
    @strawberry.mutation(permission_classes=[IsAuthenticated])
    def create_cipher(
        self, info: strawberry.Info, input: CreateCipherInput
    ) -> CipherCreatePayload:
        user = info.context.request.user
        cipher = create_cipher(
            owner=user,
            type=input.type.value,
            name=input.name,
            key=input.key,
            data=input.data,
        )

        return CipherCreateSuccess(
            cipher=Cipher(
                uuid=cipher.uuid,
                owner_id=cipher.owner.uuid,
                type=cipher.type,
                name=cipher.name,
                key=cipher.key,
                data=cipher.data.to_json(),
                created=cipher.created,
            )
        )
