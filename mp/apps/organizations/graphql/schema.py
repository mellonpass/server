import strawberry

from mp.apps.organizations.graphql.queries import OrganizationQuery


@strawberry.type
class Query(OrganizationQuery): ...
