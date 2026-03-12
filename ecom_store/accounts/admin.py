from django.contrib import admin
from django.contrib.auth import get_user_model
from config.admin import SuperuserOnlyAdmin

# Register your models here.
@admin.action(description="Soft delete (nonaktifkan user)")
def soft_delete_users(modeladmin, request, queryset):
    if not request.user.is_superuser:
        modeladmin.message_user(
            request,
            "Hanya superuser yang boleh soft delete",
            level=messages.ERROR,
        )
        return
    
    for user in queryset:
        user.soft_delete()
        
@admin.action(description="Hard delete (PERMANEN)")
def hard_delete_users(modeladmin, request, queryset):
    if not request.user.is_superuser:
        modeladmin.message_user(
            request,
            "Hanya superuser yang boleh hard delete",
            level=messages.ERROR,
        )
        return

    for user in queryset:
        user.hard_delete()
        
@admin.register(get_user_model())
class CustomUserAdmin(SuperuserOnlyAdmin):
    actions = [soft_delete_users, hard_delete_users]
    
    list_display = ["id", "username","email", "phone_number", "is_active", "is_superuser", "is_staff"]
    list_filter = ["is_staff", "is_superuser", "is_active"]
    search_fields = ["username", "email"]
    
    def has_delete_permission(self, request, obj=None):
        return False