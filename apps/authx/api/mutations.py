import strawberry
from apps.authx.services import create_user
from apps.authx.api.types import CreateUserInput, User


@strawberry.type
class UserMutation:
    @strawberry.mutation
    def create(self, info, input: CreateUserInput) -> User:
        user_dict = strawberry.asdict(input)
        user = create_user(**user_dict)
        return User(uuid=user.uuid, name=user.name, email=user.email)
