import json

from config.admin import ReadOnlyForStaffMixin
from django.contrib import admin
from django.utils.safestring import mark_safe

from .models import CheckoutSession, Order, OrderItem, OrderShipping, ShippingInsurance


# Register your models here.
@admin.register(ShippingInsurance)
class ShippingInsuranceAdmin(ReadOnlyForStaffMixin):
    list_display = ["id", "shipping", "rate", "admin_fee"]
    list_filter = ["created_at"]
    search_fields = ["shipping"]
    readonly_fields = ["created_at", "updated_at"]
    date_hierarchy = "created_at"


@admin.register(CheckoutSession)
class CheckoutSessionAdmin(ReadOnlyForStaffMixin):
    list_display = [
        "id",
        "username",
        "show_json_cart_ids",
        "store_name",
        "destination_address",
        "expires_at",
    ]
    list_filter = ["created_at"]
    search_fields = ["user__username", "store__name"]
    readonly_fields = ["created_at", "updated_at"]
    date_hierarchy = "created_at"

    def username(self, obj):
        return obj.user.username

    username.short_description = "Username"

    def store_name(self, obj):
        return obj.store.name

    store_name.short_description = "Store Name"

    def destination_address(self, obj):
        return f"{obj.destination.province} - {obj.destination.city} - {obj.destination.district}"

    destination_address.short_description = "Destination"

    def show_json_cart_ids(self, obj):
        data = json.dumps(obj.cart_ids, indent=2)
        return mark_safe(
            f'<pre style="max-height: 100px; overflow: auto;">{data}</pre>'
        )

    show_json_cart_ids.short_description = "Cart IDs"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("user", "store", "destination")


@admin.register(OrderItem)
class OrderItemAdmin(ReadOnlyForStaffMixin):
    list_display = [
        "id",
        "order_id",
        "product_name",
        "product_price",
        "qty",
        "subtotal",
    ]
    list_filter = ["is_archived", "created_at"]
    search_fields = ["product__name"]
    readonly_fields = ["created_at", "updated_at", "subtotal"]
    date_hierarchy = "created_at"

    def order_id(self, obj):
        return obj.order.order_id

    order_id.short_description = "Order ID"

    def product_name(self, obj):
        return obj.product.name

    product_name.short_description = "Product Name"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("order", "product")


@admin.register(Order)
class OrderAdmin(ReadOnlyForStaffMixin):
    list_display = [
        "order_id",
        "username",
        "store_name",
        "status",
        "payment_status",
        "payment_method",
        "grand_total_display",
        "net_income_display",
        "actual_net_income_display",
        "created_at",
    ]
    list_filter = [
        "status",
        "payment_status",
        "payment_method",
        "store",
        "created_at",
    ]
    search_fields = [
        "order_id",
        "shipping__order_no_ro",
        "shipping__order_id_ro",
        "user__username",
        "user__email",
        "store__name",
    ]
    readonly_fields = [
        "order_id",
        "grand_total",
        "net_income",
        "actual_net_income",
        "delivered_at",
        "canceled_at",
        "created_at",
        "updated_at",
    ]
    date_hierarchy = "created_at"

    def username(self, obj):
        return obj.user.username

    username.short_description = "Username"

    def store_name(self, obj):
        return obj.store.name

    store_name.short_description = "Store Name"

    def grand_total_display(self, obj):
        return f"Rp {obj.grand_total:,}"

    grand_total_display.short_description = "Grand Total"

    def net_income_display(self, obj):
        return f"Rp {obj.net_income:,}"

    net_income_display.short_description = "Net Income"

    def actual_net_income_display(self, obj):
        return f"Rp {obj.actual_net_income:,}"

    actual_net_income_display.short_description = "Actual Net Income"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("user", "store", "shipping")


@admin.register(OrderShipping)
class OrderShippingAdmin(ReadOnlyForStaffMixin):
    list_display = [
        "order_id",
        "shipping_name",
        "service_name",
        "shipping_cost_display",
        "shipping_cashback_display",
        "shipping_cost_net_display",
        "insurance_value_display",
        "shipping_weight",
        "etd",
        "created_at",
    ]
    list_filter = [
        "shipping_name",
        "service_name",
        "created_at",
    ]
    search_fields = [
        "order__order_id",
        "order_id_ro",
        "order_no_ro",
        "origin_address",
        "destination_address",
    ]
    readonly_fields = [
        "order",
        "shipping_weight",
        "insurance_value",
        "shipping_cost_net",
        "created_at",
        "updated_at",
    ]
    date_hierarchy = "created_at"

    def order_id(self, obj):
        return obj.order.order_id

    order_id.short_description = "Order ID"

    def shipping_cost_display(self, obj):
        return f"Rp {obj.shipping_cost:,}"

    shipping_cost_display.short_description = "Shipping Cost"

    def shipping_cashback_display(self, obj):
        return f"Rp {obj.shipping_cashback:,}"

    shipping_cashback_display.short_description = "Cashback"

    def shipping_cost_net_display(self, obj):
        return f"Rp {obj.shipping_cost_net:,}"

    shipping_cost_net_display.short_description = "Net Shipping Cost"

    def insurance_value_display(self, obj):
        return f"Rp {obj.insurance_value:,}"

    insurance_value_display.short_description = "Insurance"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("order", "order__user", "order__store")
