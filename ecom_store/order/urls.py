from django.urls import path

from .views_order_process import (
    CheckoutView,
    MidtransWebhookView,
    ShippingRates,
    TransactionView,
    RefundRequestCreateView
)
from .views_order_user import GetOrderByFilter, GetOrderDetail, RefundRequestByItemView

urlpatterns = [
    path("checkout/", CheckoutView.as_view(), name="checkout"),
    path("shipping-rates/", ShippingRates.as_view(), name="shipping_rates"),
    path("transaction/", TransactionView.as_view(), name="transaction"),
    path("midtrans/webhook/", MidtransWebhookView.as_view(), name="midtrans_webhook"),
    path("", GetOrderByFilter.as_view(), name="order"),
    path("<uuid:order_id>/", GetOrderDetail.as_view(), name="order_detail"),
    path("refund-requests/", RefundRequestCreateView.as_view(), name="refund_request_create"),
    path(
        "order-items/<int:order_item_id>/refund-requests/",
        RefundRequestByItemView.as_view(),
        name="refund_request_by_item",
    ),
]