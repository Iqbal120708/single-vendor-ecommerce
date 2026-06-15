from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        # Sudah ditangani DRF — normalisasi formatnya
        if isinstance(response.data, dict):
            # Kalau ada 'non_field_errors', angkat ke 'detail'
            non_field = response.data.pop("non_field_errors", None)
            if non_field and "detail" not in response.data:
                response.data["detail"] = (
                    non_field[0] if isinstance(non_field, list) else non_field
                )

            # Kalau sama sekali tidak ada 'detail' dan hanya ada 1 key error field
            # biarkan as-is (validation errors per field tetap standar DRF)

        elif isinstance(response.data, list):
            response.data = {"detail": response.data[0]}

    return response


def error_response(detail=None, errors=None, status_code=status.HTTP_400_BAD_REQUEST):
    """
    - detail: pesan error umum (string)
    - errors: field-level errors (dict), e.g. {"cart_ids": ["..."]}
    """
    body = {}
    if detail:
        body["detail"] = detail
    if errors:
        body = errors
    return Response(body, status=status_code)
