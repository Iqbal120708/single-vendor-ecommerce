from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from allauth.account.models import EmailConfirmationHMAC
from .log_utils import log_refresh_success, log_refresh_failure
import jwt
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework.permissions import AllowAny

class CustomVerifyEmailAPIView(APIView):
    """
    Menerima key verifikasi email dari URL tanpa redirect (JSON response only).
    Hanya menerima POST.
    """
    permission_classes = [AllowAny]

    http_method_names = ['post']

    def post(self, request, key, *args, **kwargs):
        try:
            email_confirmation = EmailConfirmationHMAC.from_key(key)
            if not email_confirmation:
                return Response(
                    {"detail": "Invalid or expired verification key."},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            email_confirmation.confirm(request)

            return Response(
                {"detail": "Email successfully confirmed."},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {"detail": f"Verification failed: {e}"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
from dj_rest_auth.jwt_auth import get_refresh_view
from rest_framework_simplejwt.tokens import UntypedToken

class CustomTokenRefreshView(get_refresh_view()):
    def finalize_response(self, request, response, *args, **kwargs):
        refresh_token_str = request.COOKIES.get("_refresh_token")
        if refresh_token_str:
            try:
                payload = UntypedToken(refresh_token_str).payload
                user_id = int(payload.get("user_id"))
            except Exception as e:
                if "invalid" in str(e):
                    user_id = None
                else:
                    # mendecode token ketika UntypedToken gagal misal karena token expired
                    payload = jwt.decode(
                        refresh_token_str,
                        api_settings.SIGNING_KEY,
                        algorithms=[api_settings.ALGORITHM],
                        options={"verify_exp": False}  
                    )
                    user_id = int(payload.get("user_id"))
                
        response = super().finalize_response(request, response, *args, **kwargs)
        if response.status_code == 200:
            log_refresh_success(request, user_id)
        elif response.status_code == 401:
            error_msg = response.data.get("detail", "Unknown error")
            log_refresh_failure(request, user_id, error_msg)
        return response