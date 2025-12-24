from cart.models import Cart
#from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status, serializers
from django.core.cache import cache
from .serializers import ShippingSerializer
from .models import Courier
import uuid
from .utils import fetch_shipping_rates_from_rajaongkir, get_destination, create_order_details, create_order_rajaongkir, create_order, create_order_item
import logging
from config.midtrans import snap
from store.models import Store
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
        
        checkout_id = str(uuid.uuid4())
        cache_key = f"shipping_payload_{request.user.id}_{checkout_id}" 
        shipping_context= {
            "origin_id": origin.city.ro_id,
            "destination_id": destination.city.ro_id,
            "origin": origin,
            "destination": destination,
        }
        order_details = create_order_details(carts)
        # simpan payload di cache (misal 10 menit)
        cache.set(cache_key, [shipping_context, order_details, store.id], 600)
        logger.info(f"Checkout ID {checkout_id} dibuat untuk User {request.user.id}. Data disimpan di cache.")
        return Response({
            "checkout_id": checkout_id,
            "shipping_options": shipping_options
        })

class TransactionView(APIView):
    def post(self, request):
        serializer = ShippingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        checkout_id = serializer.data["checkout_id"]
        cache_data = cache.get(f"shipping_payload_{request.user.id}_{checkout_id}")
        
        if not cache_data:
            return Response(
                {"error": "Sesi telah berakhir atau tidak ditemukan. Silakan ulangi proses (Maks. 10 menit)."}, 
                status=status.HTTP_408_REQUEST_TIMEOUT
            )
            
        shipping_context, order_details, store_id = cache_data
        
        store = Store.objects.get(id=store_id)
        # shipping_option = serializer.data
        order = create_order(request.user, shipping_context, serializer.data, store, order_details)
        order_item = create_order_item(order, order_details)
        
        item_details = []

        # Produk
        for item in order_item:
            item_details.append({
                "id": item.product_name,
                "price": int(item.product_price),
                "quantity": item.qty,
                "name": item.product_name
            })
        
        # Ongkir
        item_details.append({
            "id": "SHIPPING",
            "price": order.shipping_cost,
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
                "first_name": request.user.username,
                "email": request.user.email,
                "phone": str(request.user.phone_number)
            }
        }
        
        snap_token = snap.create_transaction(transaction)["token"]
        
        return Response({
            "snap_token": snap_token
        })
        
        