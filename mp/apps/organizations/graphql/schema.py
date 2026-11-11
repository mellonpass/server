import strawberry

from mp.apps.organizations.graphql.mutations import OrganizationMutation
from mp.apps.organizations.graphql.queries import OrganizationQuery


@strawberry.type
class Mutation:
    @strawberry.field
    def organization(self) -> OrganizationMutation:
        return OrganizationMutation()


@strawberry.type
class Query(OrganizationQuery): ...
