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
from django.contrib.auth.decorators import login_required
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path("", login_required(TemplateView.as_view(template_name="vault/index.html"))),
    path("login", TemplateView.as_view(template_name="vault/login.html")),

    # API related views.
    # ------------------------------------------------------------------------
    path("accounts/", include("mp.apps.authx.urls")),
    # Don't append with slash should be requested like:
    #   POST localhost:8000/graphql
    path("graphql", include("mp.graphql.urls")),

    # ------------------------------------------------------------------------
    path("admin", admin.site.urls),
]
