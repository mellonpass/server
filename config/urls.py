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
from django.views.decorators.csrf import csrf_exempt

from mp.authx.views import account_view, auth_view, logout_view
from mp.core.graphql.views import mp_graphql_view
from mp.jwt.views import refresh_token_view

urlpatterns = [
    path("accounts", view=account_view, name="account"),
    path("admin/", admin.site.urls),
    path("auth", view=auth_view, name="auth-login"),
    path("graphql", csrf_exempt(mp_graphql_view)),
    path("logout", view=logout_view, name="auth-logout"),
    path("refresh-token", view=refresh_token_view, name="auth-refresh-token"),
]
