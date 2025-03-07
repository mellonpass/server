from django.conf import settings
from django.http import HttpRequest
from django.utils.decorators import classonlymethod
from strawberry.django.views import GraphQLView
from strawberry.http import GraphQLHTTPResponse
from strawberry.types import ExecutionResult

from api.graphql.schema import schema


class MPGrahpQLView(GraphQLView):

    def process_result(
        self, request: HttpRequest, result: ExecutionResult
    ) -> GraphQLHTTPResponse:
        data: GraphQLHTTPResponse = {"data": result.data}

        if result.errors:
            data["errors"] = [err.formatted for err in result.errors]
            # No need to return data on errors.
            del data["data"]

        return data

    @classonlymethod
    def as_view(cls, **initkwargs):
        view = super().as_view(**initkwargs)
        view.__name__ = "mp_graphql_view"

        return view


mp_graphql_view = MPGrahpQLView.as_view(
    schema=schema,
    allow_queries_via_get=False,
    graphql_ide="graphiql" if settings.DEBUG else None,
)
