import logging
import re

import requests
from cart.models import Cart
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.timezone import localtime, now
from product.models import Product
from rest_framework import serializers
from rest_framework.exceptions import APIException, NotFound

# from shipping_address.utils import format_address
from store.models import Store, StoreShippingOption

from .models import CheckoutSession, Order, OrderItem


class RajaOngkirException(APIException):
    status_code = 502
    default_detail = "Shipping service unavailable."

class CheckoutExpired(APIException):
    status_code = 408
    default_detail = "Sesi telah berakhir atau tidak ditemukan. Silakan ulangi proses (Maks. 10 menit)."

logger = logging.getLogger("order")
logger_error = logging.getLogger("order_error")


def extract_min_etd(etd):
    """
    '3-5 day' -> 3
    '1-2 hours' -> 0
    '-' atau '' -> 999
    """
    etd = etd.lower()

    if "hour" in etd:
        return 0

    match = re.search(r"\d+", etd)
    if match is None:
        return 999
        
    return int(match.group())


def has_valid_etd(shipping):
    etd = shipping.get("etd", "")
    return bool(re.search(r"\d+", etd))


def get_active_shipping(shippings):
    shipping_names = [shipping.get("shipping_name", "") for shipping in shippings]

    active_names = StoreShippingOption.objects.filter(
        shipping_name__in=shipping_names, is_active=True
    ).values_list("shipping_name", flat=True)

    couriers = [courier for courier in active_names]

    return [
        shipping
        for shipping in shippings
        if shipping.get("shipping_name", "") in couriers
    ]


def get_best_shipping(shippings, is_cod):
    if not shippings:
        return None

    shippings = get_active_shipping(shippings)

    valid_shippings = [shipping for shipping in shippings if has_valid_etd(shipping)]

    if valid_shippings:
        shippings = valid_shippings

    if is_cod:
        cod_shippings = [shipping for shipping in shippings if shipping["is_cod"]]

        shippings = cod_shippings

    if not shippings:
        return None

    return min(
        shippings,
        key=lambda shipping: (
            shipping["shipping_cost_net"],
            extract_min_etd(shipping["etd"]),
        ),
    )


def fetch_shipping_rates_from_rajaongkir(params, is_cod):
    headers = {"x-api-key": settings.API_KEY_RAJA_ONGKIR_SHIPPING_DELIVERY}

    url = "https://api-sandbox.collaborator.komerce.id/tariff/api/v1/calculate"

    try:
        res = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=10,
        )

        res.raise_for_status()

    except requests.Timeout:
        raise RajaOngkirException("Shipping provider timeout.")

    except requests.ConnectionError:
        raise RajaOngkirException("Cannot connect to shipping provider.")

    except requests.HTTPError:
        raise RajaOngkirException(f"Shipping provider returned {res.status_code}.")

    try:
        payload = res.json()
    except ValueError:
        raise RajaOngkirException("Invalid response from shipping provider.")

    meta = payload.get("meta", {})
    data = payload.get("data", {})

    if meta.get("status") != "success":
        raise RajaOngkirException(meta.get("message", "Shipping calculation failed."))

    return {
        "reguler": get_best_shipping(data.get("calculate_reguler", []), is_cod),
        "cargo": get_best_shipping(data.get("calculate_cargo", []), is_cod),
        "instant": get_best_shipping(data.get("calculate_instant", []), is_cod),
    }


def get_destination(user, shipping_address_id=None):
    if shipping_address_id:
        destination = user.shippingaddress_set.filter(id=shipping_address_id).first()
        if destination is None:
            logger.warning(
                f"Shipping address tidak ditemukan. User ID: {user.id}, Address ID: {shipping_address_id}"
            )
            raise serializers.ValidationError(
                {"detail": "Alamat pengiriman tidak ditemukan."}
            )
    else:
        destination = user.shippingaddress_set.filter(is_default=True).first()
        if destination is None:
            logger.warning(f"Default address tidak ditemukan. User ID: {user.id}")
            raise serializers.ValidationError(
                {
                    "detail": "Belum ada alamat pengiriman. Silakan tambahkan alamat terlebih dahulu."
                }
            )

    return destination


# def create_order_details(order_items):
#     order_details = []

#     for item in order_items:
#         product = item.product

#         order_details.append(
#             {
#                 "product_name": product.name,
#                 "product_variant_name": product.variant_name,
#                 "product_price": int(product.price),
#                 "product_weight": product.weight,
#                 "product_width": product.width,
#                 "product_height": product.height,
#                 "product_length": product.length,
#                 "qty": item.qty,
#                 "subtotal": int(item.product_price) * item.qty,
#             }
#         )

#     return order_details


# def create_order(
#     checkout,
#     serializer_data,
#     payment_method="BANK TRANSFER",
# ):

#     shipping_cost = serializer_data["cost"]
#     shipping_cashback = 0
#     # insurance_value = calculate_insurance_value(order_details)
#     service_fee = 0
#     additional_cost = 0

#     order = Order.objects.create(
#         user=checkout.user,
#         store=checkout.store,
#         shipping_cost=shipping_cost,
#         shipping_cashback=shipping_cashback,
#         courier_code=serializer_data["code"],
#         shipping_type=serializer_data["service"],
#         payment_method=payment_method,
#         service_fee=service_fee,
#         additional_cost=additional_cost,
#         # insurance_value=insurance_value,
#         origin_ro=checkout.store.shipping_address.district.ro_id,
#         origin_address=checkout.store.shipping_address.formatted_address,
#         destination_ro=checkout.destination.district.ro_id,
#         destination_address=checkout.destination.formatted_address,
#     )

#     return order


# def create_order_item(order, carts):
#     results = []
#     for cart in carts:
#         order_item = OrderItem.objects.create(
#             order=order,
#             product=cart.product,
#             product_price=cart.product.price,
#             qty=cart.qty,
#         )
#         results.append(order_item)
#     return results


# belum selesai
def fetch_order_rajaongkir(order):
    order_details = create_order_details(order.items.all())

    additional_cost = order.additional_cost
    if order.store.insurance_paid_by_customer:
        additional_cost += order.insurance_value

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
        "shipping": order.shipping_name,
        "shipping_type": order.service_name,
        "payment_method": order.payment_method,
        "shipping_cost": order.shipping_cost,
        "shipping_cashback": order.shipping_cashback,
        "service_fee": order.service_fee,
        "additional_cost": additional_cost,
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
        Product.objects.select_for_update().filter(id__in=product_ids).order_by("id")
    )

    product_map = {p.id: p for p in products}

    for item in order_items:
        product = product_map[item.product_id]

        if product.stock < item.qty:
            raise ValueError("Stok tidak mencukupi")

        product.stock -= item.qty
        product.reserved_stock -= item.qty
        product.save(update_fields=["stock", "reserved_stock"])


def get_valid_checkout(user, checkout_id):
    try:
        checkout = (
            CheckoutSession.objects.select_related(
                "destination", "store", "user", "order"
            )
            .prefetch_related("order__items")
            .get(id=checkout_id, user=user)
        )
    except CheckoutSession.DoesNotExist:
        logger_error.error(
            "CheckoutSession not found",
            extra={
                "event_type": "transaction",
                "checkout_id": checkout_id,
            },
        )
        raise NotFound("CheckoutSession tidak ditemukan")

    # VALIDASI DATA CheckoutSession, return error jika expired
    if now() >= checkout.expires_at:
        raise CheckoutExpired()

    return checkout


def get_valid_carts(user, cart_ids):
    carts = Cart.objects.filter(user=user, pk__in=cart_ids).select_related("product")

    # VALIDASI DATA Cart, jika ada yang missing id return error
    found_ids = set(carts.values_list("id", flat=True))
    requested_ids = set(cart_ids)
    missing_ids = requested_ids - found_ids
    if missing_ids:
        raise serializers.ValidationError(
            {"cart_ids": (f"Cart IDs not found: {list(missing_ids)}")}
        )

    return carts


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
