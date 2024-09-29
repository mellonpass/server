"""
URL configuration for api project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path
from strawberry.django.views import GraphQLView

from api.v1.schema import schema
from apps.authx.views import account_view, auth_view, logout_view
from apps.jwt.views import refresh_token_view

urlpatterns = [
    path("accounts", view=account_view),
    path("admin/", admin.site.urls),
    path("auth", view=auth_view),
    path("graphql/v1", GraphQLView.as_view(schema=schema)),
    path("logout", view=logout_view),
    path("refresh-token", view=refresh_token_view),
]
