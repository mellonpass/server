import strawberry


@strawberry.type
class Query:
    @strawberry.field
    def version(self) -> str:
        return "v1"


schema = strawberry.Schema(Query)
