import logging
from http import HTTPStatus

from django.db import DatabaseError, InterfaceError, connection
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


@never_cache
@require_GET
def healthz_view(request: HttpRequest) -> JsonResponse:  # noqa: ARG001
    """Return 200 OK when the application and database are reachable."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except (DatabaseError, InterfaceError):
        logger.exception("Health check failed: database connectivity error.")
        return JsonResponse(
            {"status": "error"},
            status=HTTPStatus.SERVICE_UNAVAILABLE,
        )

    return JsonResponse(
        {"status": "ok"},
        status=HTTPStatus.OK,
    )
