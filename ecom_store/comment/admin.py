from django.contrib import admin
from .models import Comment

# Register your models here.
@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["id", "username", "product_name", "rating", "content", "is_archived"]
    list_filter = ["product__name", "rating", "is_archived", "created_at"]
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