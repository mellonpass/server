import json
from http import HTTPStatus
from typing import List

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.utils.module_loading import import_string
from strawberry.django.views import GraphQLView

from mp.core.utils.http import REQUEST_FORBIDDEN, UNAUTHORIZED_REQUEST
from mp.jwt.services import verify_jwt


# TODO: add a unit test.
class JWTAuthTokenMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request: HttpRequest, view_func, view_args, view_kwargs):
        if not settings.JWT_AUTH_ENABLE:
            return

        if view_func.__name__ not in [
            import_string(view_path).__name__
            for view_path in settings.JWT_AUTH_PROTECTD_VIEWS
        ]:
            return

        jwt_token = request.headers.get("Authorization", None).split(" ")[1]
        # check if access token header is present.
        if jwt_token in ["", None]:
            return JsonResponse(
                {"error": "You're not logged in.", "code": UNAUTHORIZED_REQUEST},
                status=HTTPStatus.UNAUTHORIZED,
            )

        is_valid, result = verify_jwt(jwt_token)
        if not is_valid:
            return JsonResponse(
                {"error": result, "code": REQUEST_FORBIDDEN},
                status=HTTPStatus.FORBIDDEN,
            )
