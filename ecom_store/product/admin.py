from django.contrib import admin
from .models import Category, Product

# Register your models here.
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "desc"]
    search_fields = ["name"]
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["id", "name","category_name", "stock", "price", "variant_name"]
    list_filter = ["category__name"]
    search_fields = ["name", "category__name"]
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("category")
        
    def category_name(self, obj):
        return obj.category.name
    category_name.short_description = "Category Name"