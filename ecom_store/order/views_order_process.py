import logging
import uuid
from datetime import timedelta

from config.exceptions import error_response
from config.midtrans import snap
from django.core.cache import cache
from django.db import transaction

# from django.http import JsonResponse
from django.utils import timezone
from product.models import Product
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from store.models import Store

from .models import CheckoutSession, Order
from .serializers import ShippingSerializer
from .services.checkout import CheckoutService
from .services.order import OrderService, OrderShippingService
from .utils import (
    fetch_shipping_rates_from_rajaongkir,
    get_destination,
    get_valid_carts,
    get_valid_checkout,
    RajaOngkirException
)
from .utils_midtrans import (
    InvalidMidtransPayload,
    InvalidMidtransSignature,
    WebhookMidtrans,
)

# from django.core.exceptions import ValidationError


logger = logging.getLogger("order")
logger_error = logging.getLogger("order_error")


class CheckoutView(APIView):

    def post(self, request):
        cart_ids = request.data.get("cart_ids")
        logger.info(
            f"User {request.user.id} memulai checkout untuk cart_ids: {cart_ids}"
        )

        if not cart_ids or not isinstance(cart_ids, list):
            return error_response(
                errors={
                    "cart_ids": ["cart_ids harus berupa list dan tidak boleh kosong."]
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if not all(isinstance(item, int) for item in cart_ids):
            return error_response(
                errors={
                    "cart_ids": [
                        "Semua item di dalam cart_ids harus berupa angka (integer)."
                    ]
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        store = Store.objects.filter(is_active=True).first()
        if not store:
            logger_error.error(
                f"Store aktif tidak ditemukan. User ID: {request.user.id}"
            )
            return error_response(
                "Toko sedang tidak aktif atau tidak tersedia.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        shipping_address_id = request.data.get("shipping_address_id")
        destination = get_destination(request.user, shipping_address_id)

        try:
            checkout = CheckoutService(
                user=request.user,
                cart_ids=cart_ids,
                destination=destination,
                store=store,
            ).execute()
        except serializers.ValidationError as e:
            logger_error.error(
                f"Gagal membuat order untuk user {request.user.id}: {dict(e.detail)}",
            )
            raise
        except Exception as e:
            logger_error.error(
                f"Gagal membuat order untuk user {request.user.id}: {e}",
            )
            return error_response(
                "Terjadi kesalahan saat membuat order.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        logger.info(
            f"Checkout Session {checkout.id} dibuat untuk User {request.user.id}. Data disimpan di model."
        )

        return Response({"checkout_id": str(checkout.id)})


class ShippingRates(APIView):
    def post(self, request):
        checkout_id = request.data.get("checkout_id")
        is_cod = request.data.get("is_cod", False)

        checkout = get_valid_checkout(request.user, checkout_id)

        order_items = checkout.order.items.all()

        total_weight = sum([item.product.weight * item.qty for item in order_items])
        total_price = sum([item.product.price * item.qty for item in order_items])

        params = {
            "shipper_destination_id": checkout.store.shipping_address.destination_id,
            "receiver_destination_id": checkout.destination.destination_id,
            "weight": total_weight / 1000,  # grams to kilograms
            "item_value": int(total_price),
            "cod": "yes",
            "origin_pin_point": checkout.store.shipping_address.get_coordinates,
            "destination_pin_point": checkout.destination.get_coordinates,
        }

        try:
            shipping_options = fetch_shipping_rates_from_rajaongkir(params, is_cod)
        except RajaOngkirException as e:
            logger_error.error(
                f"Gagal mengambil ongkir RajaOngkir untuk User {request.user.id}. Error: {e.detail}",
                extra={
                    "event_type": "shippingrates",
                    "checkout_id": checkout.id,
                    "weight": params["weight"],
                    "item_value": params["item_value"],
                },
            )
            raise

        return Response({"shipping_options": shipping_options})


class TransactionView(APIView):
    def post(self, request):
        serializer = ShippingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        logger.info(
            f"User {request.user.id} membuat transaksi untuk checkout_id: {serializer.validated_data["checkout_id"]}"
        )

        checkout_id = serializer.validated_data.get("checkout_id")
        checkout = get_valid_checkout(request.user, checkout_id)

        order = checkout.order
        order_item = order.items.all().select_related("product")

        try:
            order_shipping = OrderShippingService(
                order, serializer.validated_data, checkout
            ).execute()
            order.refresh_from_db()
        except Exception as e:
            logger_error.error(
                f"Gagal membuat order shipping untuk user {request.user.id}: {e}",
                extra={
                    "event_type": "transaction",
                    "checkout_id": checkout.id,
                    "order_id": order.order_id,
                },
            )
            return error_response(
                "Terjadi kesalahan saat membuat order shipping.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        item_details = []

        # Produk
        for item in order_item:
            item_details.append(
                {
                    "id": item.product.name,
                    "price": int(item.product_price),
                    "quantity": item.qty,
                    "name": item.product.name,
                }
            )

        # Ongkir
        item_details.append(
            {
                "id": "SHIPPING",
                "price": order.shipping.shipping_cost,
                "quantity": 1,
                "name": f"Ongkir {order.shipping.shipping_name} {order.shipping.service_name}",
            }
        )

        if (
            checkout.store.insurance_paid_by_customer
            and order.shipping.insurance_value > 0
        ):
            item_details.append(
                {
                    "id": "INSURANCE",
                    "price": int(order.shipping.insurance_value),
                    "quantity": 1,
                    "name": "Asuransi Pengiriman",
                }
            )

        if order.shipping.additional_cost > 0:
            item_details.append(
                {
                    "id": "ADDITIONAL COST",
                    "price": int(order.shipping.additional_cost),
                    "quantity": 1,
                    "name": "Biaya Tambahan",
                }
            )

        if order.shipping.service_fee > 0:
            item_details.append(
                {
                    "id": "SERVICE",
                    "price": int(order.shipping.service_fee),
                    "quantity": 1,
                    "name": "Biaya Servis",
                }
            )

        gross_amount = sum(item["price"] * item["quantity"] for item in item_details)
        if gross_amount != order.grand_total:
            logger_error.error(
                f"Mismatch gross_amount: {gross_amount} vs grand_total: {order.grand_total}, order_id: {order.order_id}"
            )
            return error_response("Terjadi kesalahan kalkulasi order.", status_code=500)

        transaction = {
            "transaction_details": {
                "order_id": str(order.order_id),
                "gross_amount": gross_amount,
            },
            "enabled_payments": [
                "gopay",
                "shopeepay",
                "qris",
                "bank_transfer",
                "cstore",
                "echannel",
            ],
            "item_details": item_details,
            "customer_details": {
                "first_name": checkout.user.username,
                "email": checkout.user.email,
                "phone": str(checkout.user.phone_number),
            },
        }

        snap_token = snap.create_transaction(transaction)["token"]

        logger.info(
            f"Transaksi Midtrans untuk order ID {order.order_id} dibuat untuk User {request.user.id}."
        )

        return Response({"snap_token": snap_token})


import hashlib
import json

from django.conf import settings

# from django.views.decorators.csrf import csrf_exempt


class MidtransWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        webhook_midtrans = WebhookMidtrans()

        try:
            payload = webhook_midtrans.validate_signature(request.body)
        except InvalidMidtransPayload as e:
            return Response({"error": str(e)}, status=400)
        except InvalidMidtransSignature as e:
            return Response({"error": str(e)}, status=403)

        logger.info(f"Webhook diterima untuk order_id: {payload['order_id']}")

        try:
            with transaction.atomic():
                webhook_midtrans.get_order()
                is_paid = webhook_midtrans.change_payment_status_order()
        except (Order.DoesNotExist, ValidationError):
            return Response({"detail": "Order tidak ditemukan"}, status=404)
        except Exception as e:
            logger_error.error(f"Webhook error: {e}")
            return Response({"detail": "Terjadi kesalahan"}, status=500)

        if is_paid:
            try:
                with transaction.atomic():
                    webhook_midtrans.reduce_stock()
            except Exception:
                logger_error.critical(
                    "Order paid tapi reduce_stock gagal - butuh review manual",
                    extra={
                        "event_type": "transaction",
                        "order_id": webhook_midtrans.order.order_id,
                    },
                )
                return Response({"detail": "Terjadi kesalahan"}, status=500)

        logger.info(
            f"Transaksi Midtrans untuk order id {payload['order_id']} berhasil di proses"
        )

        return Response({"detail": "OK"}, status=200)
