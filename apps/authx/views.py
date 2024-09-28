import json
from http import HTTPStatus

from django.db.utils import IntegrityError
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from marshmallow import ValidationError

from apps.authx.serializers import AccountCreateSerializer
from apps.authx.services import create_account


@require_POST
@csrf_exempt
def account_view(request: HttpRequest, *args, **kwargs):
    if request.content_type != "application/json":
        return JsonResponse(
            {"message": "Invalid request content-type."}, status=HTTPStatus.BAD_REQUEST
        )

    try:
        serializer = AccountCreateSerializer()
        account_data = serializer.load(json.loads(request.body))
        user = create_account(**account_data)
        return JsonResponse(serializer.dump(user), status=HTTPStatus.CREATED)
    except ValidationError as error:
        return JsonResponse({"error": error.messages}, status=HTTPStatus.BAD_REQUEST)
    except IntegrityError as error:
        return JsonResponse(
            {"error": f"Email {account_data['email']} already exists."},
            status=HTTPStatus.BAD_REQUEST,
        )
