from django.utils.decorators import classonlymethod
from strawberry.django.views import GraphQLView

from api.graphql.schema import schema


class MPGrahpQLView(GraphQLView):

    @classonlymethod
    def as_view(cls, **initkwargs):
        view = super().as_view(**initkwargs)
        view.__name__ = "mp_graphql_view"

        return view


mp_graphql_view = MPGrahpQLView.as_view(schema=schema, allow_queries_via_get=False)
