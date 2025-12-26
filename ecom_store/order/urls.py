from django.urls import path

from .views import CheckoutView, TransactionView, midtrans_webhook

urlpatterns = [
    path("checkout/", CheckoutView.as_view(), name="checkout"),
    path("transaction/", TransactionView.as_view(), name="transaction"),
    path("midtrans/webhook/", midtrans_webhook, name="midtrans_webhook"),
]
