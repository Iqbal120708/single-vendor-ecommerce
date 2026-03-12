from django.contrib import admin
from .models import Cart
from config.admin import ReadOnlyForStaffMixin

# Register your models here.
@admin.register(Cart)
class CartAdmin(ReadOnlyForStaffMixin):
    list_display = ["id", "username","product_name", "qty"]
    list_filter = ["product__name", "created_at"]
    search_fields = ["user__username", "user__email", "product__name"]
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    def username(self, obj):
        return obj.user.username
    username.short_description = "Username"
        
    def product_name(self, obj):
        return obj.product.name
    product_name.short_description = "Product Name"
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("user", "product")