from django.contrib import admin
from .models import Province, City, District, SubDistrict, ShippingAddress
from config.admin import ReadOnlyForStaffMixin

# Register your models here.
@admin.register(Province)
class ProvinceAdmin(ReadOnlyForStaffMixin):
    list_display = ["ro_id", "name"]
    search_fields = ["ro_id", "name"]
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
@admin.register(City)
class CityAdmin(ReadOnlyForStaffMixin):
    list_display = ["ro_id", "name", "province_name"]
    search_fields = ["ro_id", "name", "province_name"]
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    def province_name(self, obj):
        return obj.province.name
    province_name.short_description = "Province Name"
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("province")
        
@admin.register(District)
class DistrictAdmin(ReadOnlyForStaffMixin):
    list_display = ["ro_id", "name", "city_name"]
    search_fields = ["ro_id", "name", "city_name"]
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    def city_name(self, obj):
        return obj.city.name
    city_name.short_description = "City Name"
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("city")
        
@admin.register(SubDistrict)
class SubDistrictAdmin(ReadOnlyForStaffMixin):
    list_display = ["ro_id", "name", "district_name", "zip_code"]
    search_fields = ["ro_id", "name", "district_name", "zip_code"]
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    def district_name(self, obj):
        return obj.district.name
    district_name.short_description = "District Name"
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("district")
        
@admin.register(ShippingAddress)
class ShippingAddressAdmin(ReadOnlyForStaffMixin):
    list_display = ["id", "username", "province_name", "city_name", "district_name", "subdistrict_name"]
    search_fields = ["username", "province_name", "city_name", "district_name", "subdistrict_name"]
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    def province_name(self, obj):
        return obj.province.name
    province_name.short_description = "Province Name"
    
    def city_name(self, obj):
        return obj.city.name
    city_name.short_description = "City Name"
    
    def district_name(self, obj):
        return obj.district.name
    district_name.short_description = "District Name"
    
    def subdistrict_name(self, obj):
        return obj.subdistrict.name
    subdistrict_name.short_description = "Subdistrict Name"
    
    def username(self, obj):
        return obj.user.username
    username.short_description = "Username"
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("province", "city", "district", "subdistrict", "user")