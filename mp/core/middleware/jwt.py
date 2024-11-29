from http import HTTPStatus

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.utils.module_loading import import_string

from mp.core.utils.http import REQUEST_FORBIDDEN, UNAUTHORIZED_REQUEST
from mp.jwt.services import verify_jwt


class JWTAuthTokenMiddleware:
    """A middleware to check for an authenticated user and a JWT Bearer
    token on the request header on certain views defined on
    JWT_AUTH_PROTECTD_VIEWS.
    """

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

        auth_header = request.headers.get("Authorization", None)

        # only allow authenticated user and request with authorization header.
        if not request.user.is_authenticated or auth_header in ["", None]:
            return JsonResponse(
                {"error": "You're not logged in.", "code": UNAUTHORIZED_REQUEST},
                status=HTTPStatus.UNAUTHORIZED,
            )

        token_type = "Bearer "
        if not auth_header.startswith(token_type):
            return JsonResponse(
                {
                    "error": "Misformatted authorization header.",
                    "code": UNAUTHORIZED_REQUEST,
                },
                status=HTTPStatus.UNAUTHORIZED,
            )

        jwt_token = auth_header.split(token_type)[1]
        is_valid, result = verify_jwt(jwt_token)

        if not is_valid:
            return JsonResponse(
                {"error": result, "code": REQUEST_FORBIDDEN},
                status=HTTPStatus.FORBIDDEN,
            )

        # make sure that the token and the user matched!
        if str(request.user.uuid) != result["sub"]:
            return JsonResponse(
                {
                    "error": (
                        "Authenticated user information doesn't match with the token data."
                    ),
                    "code": REQUEST_FORBIDDEN,
                },
                status=HTTPStatus.FORBIDDEN,
            )
