from decimal import Decimal

from django.core.validators import MinValueValidator
from rest_framework import serializers

from .models import Order, OrderItem, OrderShipping, RefundRequest
from .tasks import send_refund_created_email


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


class OrderShippingSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderShipping
        fields = [
            "shipping_name",
            "service_name",
            "shipping_weight",
            "etd",
            "shipping_cost",
            "shipping_cashback",
            "shipping_cost_net",
            "insurance_value",
            "service_fee",
            "additional_cost",
            "origin_address",
            "destination_address",
            # "order_no_ro",
            "cod_value",
            "tracking_number",
        ]
        read_only_fields = fields


class OrderSerializer(serializers.ModelSerializer):
    shipping = OrderShippingSerializer(read_only=True)

    class Meta:
        model = Order
        fields = [
            "order_id",
            "status",
            "payment_status",
            "payment_method",
            "delivered_at",
            "created_at",
            "grand_total",
            "net_income",
            "actual_net_income",
            "shipping",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.read_only = True


class RefundRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RefundRequest
        fields = [
            "id", "order_item", "amount", "reason", "note",
            "destination_type", "destination_provider", "destination_number",
            "account_holder_name", "status", "requested_at",
        ]
        read_only_fields = ["id", "amount", "reason", "status", "requested_at"]

    def validate_order_item(self, order_item):
        request = self.context["request"]
        if order_item.order.user_id != request.user.id:
            raise serializers.ValidationError("Item ini bukan milik order Anda.")
        if order_item.has_active_refund:
            raise serializers.ValidationError("Sudah ada refund request aktif untuk item ini.")
        return order_item

    def validate(self, data):
        provider = data.get("destination_provider")
        destination_type = data.get("destination_type")

        if destination_type == RefundRequest.DestinationType.BANK:
            if provider not in RefundRequest.BANK_PROVIDERS:
                raise serializers.ValidationError({"destination_provider": "Pilih bank yang valid."})
        elif destination_type == RefundRequest.DestinationType.EWALLET:
            if provider not in RefundRequest.EWALLET_PROVIDERS:
                raise serializers.ValidationError({"destination_provider": "Pilih e-wallet yang valid."})

        order = data["order_item"].order

        if not hasattr(order, "shipping"):
            raise serializers.ValidationError(
                "Order belum menyelesaikan proses checkout -- refund tidak dapat diajukan."
            )
        
        return data

    def create(self, validated_data):
        order_item = validated_data["order_item"]
        order_status = order_item.order.status

        if order_status in [order_item.order.Status.PENDING, order_item.order.Status.PROCESSING]:
            reason = RefundRequest.Reason.CUSTOMER_CANCEL
        elif order_status in [order_item.order.Status.SHIPPED, order_item.order.Status.DELIVERED]:
            reason = RefundRequest.Reason.RETURN
        else:
            raise serializers.ValidationError(
                f"Order dengan status {order_status} tidak bisa diajukan refund."
            )

        validated_data["reason"] = reason
        validated_data["amount"] = order_item.subtotal
        refund_request = super().create(validated_data)

        send_refund_created_email.delay(refund_request.id)

        return refund_request


class RefundRequestDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = RefundRequest
        fields = [
            "id", "order_item", "amount", "reason", "note", "status",
            "destination_type", "destination_provider", "destination_number",
            "account_holder_name",
            "requested_at", "approved_at", "completed_at",
        ]
        read_only_fields = fields