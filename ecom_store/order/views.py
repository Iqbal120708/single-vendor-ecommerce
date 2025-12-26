from cart.models import Cart
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status, serializers
from django.core.cache import cache
from .serializers import ShippingSerializer
from .models import Courier, CheckoutSession
import uuid
from .utils import fetch_shipping_rates_from_rajaongkir, get_destination, create_order, create_order_item
from .utils_midtrans import WebhookMidtrans, InvalidMidtransPayload, InvalidMidtransSignature
import logging
from config.midtrans import snap
from store.models import Store
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from django.http import JsonResponse

logger = logging.getLogger("order")
logger_error = logging.getLogger("order_error")

class CheckoutView(APIView):

    def post(self, request):
        cart_ids = request.data.get("cart_ids")
        logger.info(f"User {request.user.id} memulai checkout untuk cart_ids: {cart_ids}")
        
        if not cart_ids or not isinstance(cart_ids, list):
            return Response(
                {"error": "cart_ids harus berupa list dan tidak boleh kosong."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not all(isinstance(item, int) for item in cart_ids):
            return Response(
                {"error": "Semua item di dalam cart_ids harus berupa angka (integer)."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        carts = (
            Cart.objects
            .filter(
                user=request.user,
                pk__in=cart_ids
            )
            .select_related("product")
        )
        
        store = Store.objects.filter(is_active=True).first()
        if not store:
            logger_error.error(f"Store aktif tidak ditemukan. User ID: {request.user.id}")
            return Response({"error": "Toko tidak ditemukan."}, status=status.HTTP_400_BAD_REQUEST)
            
        origin = store.shipping_address

        shipping_address_id = request.data.get("shipping_address_id")
        destination = get_destination(
            request.user, shipping_address_id
        )
        total_weight = sum([cart.product.weight*cart.qty for cart in carts])
        couriers = Courier.objects.filter(is_active=True).values_list("code", flat=True)
        
        payload = {
            "origin": origin.district.ro_id,
            "destination": destination.district.ro_id,
            "weight": total_weight,
            "courier": ":".join(list(couriers))
        }
        try:
            shipping_options = fetch_shipping_rates_from_rajaongkir(payload)
        except serializers.ValidationError as e:
            payload["event_type"] = "checkout"
            logger_error.error(
                f"Gagal mengambil ongkir RajaOngkir untuk User {request.user.id}. Error: {e.detail["error"]}",
                extra=payload
            )
            raise
        
        checkout = CheckoutSession.objects.create(
            user=request.user,
            cart_ids=cart_ids,
            destination=destination,
            store=store,
            expires_at=timezone.now() + timedelta(minutes=10)
        )

        # checkout_id = str(uuid.uuid4())
        
        # cache_key = f"shipping_payload_{request.user.id}_{checkout_id}" 
        # shipping_context= {
        #     "origin_id": origin.city.ro_id,
        #     "destination_id": destination.city.ro_id,
        #     "origin": origin,
        #     "destination": destination,
        # }
        # order_details = create_order_details(carts)
        # # simpan payload di cache (misal 10 menit)
        # cache.set(cache_key, [shipping_context, order_details, store.id], 600)
        logger.info(f"Checkout Session {checkout.id} dibuat untuk User {request.user.id}. Data disimpan di model.")
        return Response({
            "checkout_id": str(checkout.id),
            "shipping_options": shipping_options
        })

class TransactionView(APIView):
    def post(self, request):
        serializer = ShippingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        checkout_id = serializer.data["checkout_id"]
        logger.info(f"User {request.user.id} membuat transaksi untuk checkout_id: {checkout_id}")
        
        try:
            checkout = (
                CheckoutSession.objects
                .select_related("destination", "store", "user")
                .get(id=checkout_id)
            )
        except CheckoutSession.DoesNotExist:
            logger_error.error(
                "CheckoutSession not found",
                extra={
                    "event_type": "transaction",
                    "checkout_id": checkout_id,
                }
            )
            return Response(
                {"detail": "CheckoutSession tidak ditemukan"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if timezone.now() >= checkout.expires_at:
            return Response(
                {"error": "Sesi telah berakhir atau tidak ditemukan. Silakan ulangi proses (Maks. 10 menit)."}, 
                status=status.HTTP_408_REQUEST_TIMEOUT
            )
            
        # shipping_context, order_details, store_id = cache_data
        
        # store = Store.objects.get(id=store_id)
        # shipping_option = serializer.data
        
        carts = (
            Cart.objects
            .filter(
                user=checkout.user,
                pk__in=checkout.cart_ids
            )
            .select_related("product")
        )
        
        order = create_order(checkout, serializer.data)
        order_item = create_order_item(order, carts)
        
        item_details = []

        # Produk
        for item in order_item:
            item_details.append({
                "id": item.product.name,
                "price": int(item.product_price),
                "quantity": item.qty,
                "name": item.product.name
            })
        
        # Ongkir
        item_details.append({
            "id": "SHIPPING",
            "price": order.shipping_cost - order.shipping_cashback,
            "quantity": 1,
            "name": f'Ongkir {order.courier_code} {order.shipping_type}'
        })
        
        if order.insurance_value > 0:
            item_details.append({
                "id": "INSURANCE",
                "price": int(order.insurance_value),
                "quantity": 1,
                "name": "Asuransi Pengiriman"
            })
        
        gross_amount = sum(
            item["price"] * item["quantity"]
            for item in item_details
        )
        
        transaction = {
            "transaction_details": {
                "order_id": str(order.order_id),
                "gross_amount": gross_amount
            },
            "item_details": item_details,
            "customer_details": {
                "first_name": checkout.user.username,
                "email": checkout.user.email,
                "phone": str(checkout.user.phone_number)
            }
        }
        
        snap_token = snap.create_transaction(transaction)["token"]
        
        logger.info(f"Transaksi Midtrans untuk order ID {order.order_id} dibuat untuk User {request.user.id}.")
        
        return Response({
            "snap_token": snap_token
        })
        
import hashlib
import json
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def midtrans_webhook(request):
    webhook_midtrans = WebhookMidtrans()
    
    try:
        payload = webhook_midtrans.validate_signature(request.body)
    except InvalidMidtransPayload as e:
        return JsonResponse({"error": str(e)}, status=400)
    except InvalidMidtransSignature as e:
        return JsonResponse({"error": str(e)}, status=403)
        
    logger.info(f"User {request.user.id} sudah melakukan transaksi untuk order_id: {payload["order_id"]}")
        
    with transaction.atomic():
        try:
            webhook_midtrans.get_order()
        except:
            return JsonResponse(
                {"detail": "Order tidak ditemukan"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            webhook_midtrans.change_payment_status_order()
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_200_OK
            )
            
        try:
            webhook_midtrans.create_order_ro()
            logger.info(f"Berhasil membuat order RajaOngkir untuk user {request.user.id} dengan order id {payload["order_id"]}")
            webhook_midtrans.update_order_from_rajaongkir_response()
            webhook_midtrans.reduce_stock()
        except Exception as e:
            raise
    
    logger.info(f"Transaksi Midtrans untuk order id {payload["order_id"]} berhasil di proses")
    
    return JsonResponse(
        {"detail": "Order berhasil diproses"},
        status=status.HTTP_201_CREATED
    )