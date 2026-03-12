from django.contrib import admin
from config.admin import ReadOnlyForStaffMixin
from .models import Courier, CheckoutSession, OrderItem, Order

# Register your models here.
@admin.register(Courier)
class CourierAdmin(ReadOnlyForStaffMixin):
    list_display = ["id", "code", "name","is_active"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "code"]
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
@admin.register(CheckoutSession)
class CheckoutSessionAdmin(ReadOnlyForStaffMixin):
    list_display = ["id", "username", "show_json_cart_ids","store_name", "destination_address", "expires_at"]
    list_filter = ["created_at"]
    search_fields = ["user__username", "store__name"]
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
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
        data = json.dumps(obj.my_json_field, indent=2)
        return mark_safe(f'<pre style="max-height: 100px; overflow: auto;">{data}</pre>')
    show_json_cart_ids.short_description = "Cart IDs"
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("user", "store", "destination")
        
@admin.register(OrderItem)
class OrderItemAdmin(ReadOnlyForStaffMixin):
    list_display = ["id", "order_id", "product_name","product_price", "qty", "subtotal"]
    list_filter = ["is_archived", "created_at"]
    search_fields = ["product__name"]
    readonly_fields = ['created_at', 'updated_at', 'subtotal']
    date_hierarchy = 'created_at'
    
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
        "courier_code",
        "grand_total",
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
        "order_no_ro",
        "user__username",
        "user__email",
        "store__name",
    ]
    readonly_fields = [
        "order_id",
        "grand_total",
        "insurance_value",
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

    def grand_total(self, obj):
        return f"Rp {obj.grand_total:,}"
    grand_total.short_description = "Grand Total"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("user", "store")