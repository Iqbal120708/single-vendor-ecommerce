from django.contrib import admin
from .models import Store
from config.admin import ReadOnlyForStaffMixin

# Register your models here.
@admin.register(Store)
class StoreAdmin(ReadOnlyForStaffMixin):
    list_display = ["id", "brand_name", "name", "email", "phone_number", "address", "is_active"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["brand_name", "name", "email", "phone_number"]
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    def address(self, obj):
        return f"{obj.shipping_address.province} - {obj.shipping_address.city} - {obj.shipping_address.district}"