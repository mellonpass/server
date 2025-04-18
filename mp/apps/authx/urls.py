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

from django.urls import path

from mp.apps.authx.views import (
    account_create_view,
    check_email_view,
    login_view,
    logout_view,
    setup_view,
    unlock_view,
    verify_view,
    whoami_view,
)

app_name = "accounts"
urlpatterns = [
    path("check-email", view=check_email_view, name="check-email"),
    path("create", view=account_create_view, name="create"),
    path("login", view=login_view, name="login"),
    path("logout", view=logout_view, name="logout"),
    path("setup", view=setup_view, name="setup"),
    path("verify", view=verify_view, name="verify"),
    path("whoami", view=whoami_view, name="whoami"),
    path("unlock", view=unlock_view, name="unlock"),
]
