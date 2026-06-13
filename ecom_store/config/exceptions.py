from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


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


def error_response(detail, status_code=status.HTTP_400_BAD_REQUEST):
    """
    Gunakan ini di view untuk manual error response.
    Selalu pakai 'detail' — konsisten dengan DRF dan library pihak ketiga.
    """
    return Response({"detail": detail}, status=status_code)