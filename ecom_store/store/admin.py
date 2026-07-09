from config.admin import ReadOnlyForStaffMixin
from django.contrib import admin

from .models import Store, StoreShippingOption


# Register your models here.
@admin.register(Store)
class StoreAdmin(ReadOnlyForStaffMixin):
    list_display = [
        "id",
        "brand_name",
        "name",
        "email",
        "phone_number",
        "address",
        "is_active",
        "enable_insurance",
        "insurance_threshold",
        "insurance_paid_by_customer",
    ]
    list_filter = [
        "is_active",
        "enable_insurance",
        "insurance_paid_by_customer",
        "created_at",
    ]
    search_fields = ["brand_name", "name", "email", "phone_number"]
    readonly_fields = ["created_at", "updated_at"]
    date_hierarchy = "created_at"

    def address(self, obj):
        return f"{obj.shipping_address.province} - {obj.shipping_address.city} - {obj.shipping_address.district}"


@admin.register(StoreShippingOption)
class StoreShippingOptionAdmin(ReadOnlyForStaffMixin):
    list_display = ["id", "store_name", "shipping_name", "is_active"]
    list_filter = ["shipping_name", "is_active"]
    search_fields = ["store__name", "shipping_name"]

    def store_name(self, obj):
        return obj.store.name

    store_name.short_description = "Store Name"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("store")