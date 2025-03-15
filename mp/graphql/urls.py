from django.urls import path
from django.views.decorators.csrf import csrf_protect

from mp.graphql.views import mp_graphql_view

urlpatterns = [
    path("", csrf_protect(mp_graphql_view)),
]
