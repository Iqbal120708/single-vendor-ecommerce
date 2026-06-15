from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from order.models import CheckoutSession
from order.utils import get_valid_carts
from product.models import Product
from rest_framework import serializers

from .order import OrderService


class CheckoutService:
    def __init__(self, user, cart_ids, destination, store):
        self.user = user
        self.cart_ids = cart_ids
        self.destination = destination
        self.store = store

    def execute(self):
        with transaction.atomic():
            checkout = CheckoutSession.objects.create(
                user=self.user,
                cart_ids=self.cart_ids,
                destination=self.destination,
                store=self.store,
                expires_at=timezone.now() + timedelta(minutes=10),
            )

            carts = get_valid_carts(self.user, checkout.cart_ids)

            self._validate_and_reserve_stock(carts)

            service = OrderService(checkout, carts)
            order = service.execute()
            checkout.order = order
            checkout.save(update_fields=["order"])

            return checkout

    def _validate_and_reserve_stock(self, carts):
        product_ids = carts.values_list("product__id", flat=True)
        products = (
            Product.objects.select_for_update()
            .filter(id__in=product_ids)
            .order_by("id")
        )

        products_map = {product.id: product for product in products}

        for cart in carts:
            product = products_map[cart.product.id]
            available_stock = product.stock - product.reserved_stock

            if available_stock < cart.qty:
                raise serializers.ValidationError(
                    {"detail": f"Stok {product.name} tidak cukup"}
                )

            product.reserved_stock += cart.qty

        Product.objects.bulk_update(products, ["reserved_stock"])
