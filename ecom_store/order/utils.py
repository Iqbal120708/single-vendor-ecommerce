import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.timezone import localtime
from .models import Courier
#from shipping_address.utils import format_address
from store.models import Store
from rest_framework import serializers
import logging
from .models import Order, OrderItem

logger = logging.getLogger("order")
logger_error = logging.getLogger("order_error")

def fetch_shipping_rates_from_rajaongkir(payload):
    headers = {"key": settings.API_KEY_RAJA_ONGKIR}
    
    results = []

    res = requests.post(
        "https://rajaongkir.komerce.id/api/v1/calculate/district/domestic-cost", data=payload, headers=headers
    )

    data = res.json()
    if res.status_code == 200:
        for item in data["data"]:
            results.append(
                {
                    "name": item["name"],
                    "code": item["code"],
                    "service": item["service"],
                    "description": item["description"],
                    "cost": item["cost"],
                    "etd": item["etd"],
                }
            )
    else:
        raise serializers.ValidationError({"error": data["meta"]["message"]})
    return results


def get_destination(user, shipping_address_id=None):
    if shipping_address_id:
        destination = user.shippingaddress_set.filter(id=shipping_address_id).first()
    else:
        destination = user.shippingaddress_set.filter(is_default=True).first()

    if not destination:
        logger.warning(
            f"Destination tidak ditemukan. User ID: {user.id}, Address ID Provided: {shipping_address_id}"
        )
        raise serializers.ValidationError({"error": "Alamat pengiriman belum dipilih. Silakan pilih salah satu alamat Anda atau atur salah satu sebagai 'Alamat Utama' (Default)."
        })
    
    return destination
    
def create_order_details(carts):
    order_details = []

    for cart in carts:
        product = cart.product
    
        order_details.append({
            "product_name": product.name,
            "product_variant_name": product.variant_name,
            "product_price": product.price,
            "product_weight": product.weight,
            "product_width": product.width,
            "product_height": product.height,
            "product_length": product.length,
            "qty": cart.qty,
            "subtotal": product.price * cart.qty,
        })
        
    return order_details
    

def create_order(user, shipping_context, shipping_option, store, order_details, payment_method="BANK TRANSFER"):
    
    shipping_cost = shipping_option["cost"]
    shipping_cashback = 0
    #insurance_value = calculate_insurance_value(order_details)
    service_fee = 0
    additional_cost = 0
    
    order = Order.objects.create(
        user=user,
        store=store,
        shipping_cost=shipping_cost,
        shipping_cashback=shipping_cashback,
        courier_code=shipping_option["code"],
        shipping_type=shipping_option["service"],
        payment_method=payment_method,
        service_fee=service_fee,
        additional_cost=additional_cost,
        #insurance_value=insurance_value,
        origin_ro=shipping_context["origin_id"],
        origin_address=shipping_context["origin"].formatted_address,
        destination_ro=shipping_context["destination_id"],
        destination_address=shipping_context["destination"].formatted_address,
    )
    
    return order
    
def create_order_item(order, order_details):
    results = []
    for item in order_details:
        order_item = OrderItem.objects.create(
            order=order,
            product_name=item["product_name"],
            product_variant_name=item["product_variant_name"],
            product_weight=item["product_weight"],
            product_price=item["product_price"],
            qty=item["qty"]
        )
        results.append(order_item)
    return results
        
# belum selesai
def create_order_rajaongkir(order, order_details):
    
    headers = {"key": settings.API_KEY_RAJA_ONGKIR}

    order_data = {
        "order_date": str(localtime(order.created_at).date()),
        "brand_name": order.store.brand_name,
        "shipper_name": order.store.name,
        "shipper_phone": order.store.clean_phone_number,
        "shipper_destination_id": order.origin_ro,
        "shipper_address": order.origin_address,
        "receiver_name": order.user.username,
        "receiver_phone": order.user.clean_phone_number,
        "receiver_destination_id": order.destination_ro,
        "receiver_address": order.destination_address,
        "shipper_email": order.store.email,
        "shipping": order.courier_code,
        "shipping_type": order.shipping_type,
        "payment_method": order.payment_method,
        "shipping_cost": order.shipping_cost,
        "shipping_cashback": order.shipping_cashback,
        "service_fee": order.service_fee,
        "additional_cost": order.additional_cost,
        "grand_total": order.grand_total,
        "cod_value": order.cod_value,
        "insurance_value": order.insurance_value,
        "order_details": order_details
        #"origin_pin_point": "-7.274631, 109.207174",
        #"destination_pin_point": "-7.274631, 109.207174",
    }
    
    res = requests.post(
        "https://api-sandbox.collaborator.komerce.id/order/api/v1/orders/store", data=order_data, headers=headers
    )