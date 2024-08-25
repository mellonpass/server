import strawberry
from apps.authx.services import create_account
from apps.authx.api.types import CreateAccountInput, Account


@strawberry.type
class AccountMutation:
    @strawberry.mutation
    def create(self, info, input: CreateAccountInput) -> Account:
        account_dict = strawberry.asdict(input)
        account = create_account(**account_dict)
        return Account(uuid=account.uuid, name=account.name, email=account.email)
