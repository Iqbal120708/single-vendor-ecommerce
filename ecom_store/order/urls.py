from django.urls import path
from .views import CheckoutView, TransactionView

urlpatterns = [
    path("checkout/", CheckoutView.as_view(), name="checkout"),
    path("transaction/", TransactionView.as_view(), name="transaction"),
]