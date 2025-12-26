import logging

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.timezone import localtime
from rest_framework import serializers

# from shipping_address.utils import format_address
from store.models import Store

from .models import Courier, Order, OrderItem

logger = logging.getLogger("order")
logger_error = logging.getLogger("order_error")


def fetch_shipping_rates_from_rajaongkir(payload):
    headers = {"key": settings.API_KEY_RAJA_ONGKIR_SHIPPING_COST}

    results = []

    res = requests.post(
        "https://rajaongkir.komerce.id/api/v1/calculate/district/domestic-cost",
        data=payload,
        headers=headers,
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
        raise serializers.ValidationError(
            {
                "error": "Alamat pengiriman belum dipilih. Silakan pilih salah satu alamat Anda atau atur salah satu sebagai 'Alamat Utama' (Default)."
            }
        )

    return destination


def create_order_details(order_items):
    order_details = []

    for item in order_items:
        product = item.product

        order_details.append(
            {
                "product_name": product.name,
                "product_variant_name": product.variant_name,
                "product_price": int(product.price),
                "product_weight": product.weight,
                "product_width": product.width,
                "product_height": product.height,
                "product_length": product.length,
                "qty": item.qty,
                "subtotal": int(item.product_price) * item.qty,
            }
        )
            
    return order_details


def create_order(
    checkout,
    serializer_data,
    payment_method="BANK TRANSFER",
):

    shipping_cost = serializer_data["cost"]
    shipping_cashback = 0
    # insurance_value = calculate_insurance_value(order_details)
    service_fee = 0
    additional_cost = 0

    order = Order.objects.create(
        user=checkout.user,
        store=checkout.store,
        shipping_cost=shipping_cost,
        shipping_cashback=shipping_cashback,
        courier_code=serializer_data["code"],
        shipping_type=serializer_data["service"],
        payment_method=payment_method,
        service_fee=service_fee,
        additional_cost=additional_cost,
        # insurance_value=insurance_value,
        origin_ro=checkout.store.shipping_address.district.ro_id,
        origin_address=checkout.store.shipping_address.formatted_address,
        destination_ro=checkout.destination.district.ro_id,
        destination_address=checkout.destination.formatted_address,
    )

    return order


def create_order_item(order, carts):
    results = []
    for cart in carts:
        order_item = OrderItem.objects.create(
            order=order,
            product=cart.product,
            product_price=cart.product.price,
            qty=cart.qty,
        )
        results.append(order_item)
    return results


# belum selesai
def fetch_order_rajaongkir(order):
    order_details = create_order_details(order.items.all())
    
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
        "order_details": order_details,
        # "origin_pin_point": "-7.274631, 109.207174",
        # "destination_pin_point": "-7.274631, 109.207174",
    }
    
    headers = {"x-api-key": settings.API_KEY_RAJA_ONGKIR_SHIPPING_DELIVERY}
    res = requests.post(
        "https://api-sandbox.collaborator.komerce.id/order/api/v1/orders/store",
        json=order_data,
        headers=headers,
    )

    return res
    
# def change_payment_status_order(order, transaction_status):
#     if transaction_status in ["settlement", "capture"]:
#         if fraud_status == "accept": 
#             order.payment_status = "paid"
#     elif transaction_status in ["deny", "cancel", "expire"]:
#         order.payment_status = "failed"
#     elif transaction_status == "refund":
#         order.payment_status = "refunded"
        
#     return order.payment_status
        
def reduce_product_stock(order_items):
    product_ids = order_items.values_list("product_id", flat=True)

    products = (
        Product.objects
        .select_for_update()
        .filter(id__in=product_ids)
    )

    product_map = {p.id: p for p in products}

    for item in order_items:
        product = product_map[item.product_id]

        if product.stock < item.qty:
            raise ValueError("Stok tidak mencukupi")

        product.stock -= item.qty
        product.save()
