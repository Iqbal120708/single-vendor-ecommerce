"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
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
from django.urls import path, include
from dj_rest_auth.urls import urlpatterns as dj_rest_auth_urls
from accounts.views import CustomTokenRefreshView, CustomVerifyEmailAPIView
from dj_rest_auth.views import PasswordResetConfirmView

for i, urlpattern in enumerate(dj_rest_auth_urls):
    if getattr(urlpattern, 'name', None) == "token_refresh":
        dj_rest_auth_urls[i] = path(
            "token/refresh/",
            CustomTokenRefreshView.as_view(),
            name="token_refresh"
        )

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include(dj_rest_auth_urls)),
    path(
        "api/auth/registration/account-confirm-email/<key>/",
        CustomVerifyEmailAPIView.as_view(),
        name="email_verified",
    ),
    path(
        "api/auth/password/reset/confirm/<uidb64>/<token>/",
        PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path("api/auth/registration/", include("dj_rest_auth.registration.urls")),
    path("api/product/", include("product.urls")),
    path("api/cart/", include("cart.urls")),
]
