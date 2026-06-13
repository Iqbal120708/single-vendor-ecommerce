from django.core.validators import MinValueValidator
from rest_framework import serializers
from decimal import Decimal
from .models import Order, OrderItem


class ShippingSerializer(serializers.Serializer):
    checkout_id = serializers.CharField(max_length=36)
    shipping_name = serializers.CharField(max_length=20)
    service_name = serializers.CharField(max_length=20)
    shipping_cost = serializers.IntegerField(validators=[MinValueValidator(0)])
    shipping_cashback = serializers.IntegerField(validators=[MinValueValidator(0)])
    shipping_cost_net = serializers.IntegerField(validators=[MinValueValidator(0)])
    shipping_weight = serializers.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0"))],
    )
    service_fee = serializers.IntegerField(validators=[MinValueValidator(0)])
    net_income = serializers.IntegerField(validators=[MinValueValidator(0)])
    is_cod = serializers.BooleanField()
    etd = serializers.CharField(max_length=10)


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    order_id = serializers.CharField(source="order.order_id", read_only=True)

    class Meta:
        model = OrderItem
        fields = ["order_id", "product_name", "subtotal", "qty", "created_at"]
        read_only_fields = ["qty", "created_at"]


class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = [
            "order_id",
            "status",
            "payment_status",
            "payment_method",
            "delivered_at",
            "canceled_at",
            "created_at",
            "courier_code",
            "shipping_type",
            "shipping_cost",
            "shipping_cashback",
            "origin_address",
            "destination_address",
            "order_no_ro",
            "service_fee",
            "insurance_value",
            "cod_value",
            "grand_total",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.read_only = True
