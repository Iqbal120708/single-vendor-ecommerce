from django.core.validators import MinValueValidator
from rest_framework import serializers

from .models import Order, OrderItem


class ShippingSerializer(serializers.Serializer):
    checkout_id = serializers.CharField(max_length=36)
    code = serializers.CharField(max_length=20)
    # name = serializers.CharField(max_length=50)
    service = serializers.CharField(max_length=20)
    # description = serializers.CharField(max_length=255)
    cost = serializers.IntegerField(validators=[MinValueValidator(1)])
    # etd = serializers.CharField(max_length=10)


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
