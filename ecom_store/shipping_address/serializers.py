import re

from rest_framework import serializers

from .models import City, District, Province, ShippingAddress, SubDistrict
from .simple_address_serializers import (SimpleCitySerializer,
                                         SimpleDistrictSerializer,
                                         SimpleProvinceSerializer,
                                         SimpleSubDistrictSerializer)


class ProvinceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Province
        fields = ["ro_id", "name"]


class CitySerializer(serializers.ModelSerializer):
    province = ProvinceSerializer(read_only=True)

    class Meta:
        model = City
        fields = ["ro_id", "name", "province"]


class DistrictSerializer(serializers.ModelSerializer):
    city = CitySerializer(read_only=True)

    class Meta:
        model = District
        fields = ["ro_id", "name", "city"]


class SubDistrictSerializer(serializers.ModelSerializer):
    district = DistrictSerializer(read_only=True)

    class Meta:
        model = SubDistrict
        fields = ["ro_id", "name", "zip_code", "district"]


class ShippingAddressSerializer(serializers.ModelSerializer):
    province = SimpleProvinceSerializer(read_only=True)
    city = SimpleCitySerializer(read_only=True)
    district = SimpleDistrictSerializer(read_only=True)
    subdistrict = SimpleSubDistrictSerializer(read_only=True)
    user = serializers.SerializerMethodField()

    province_name = serializers.CharField(max_length=100, write_only=True)
    city_name = serializers.CharField(max_length=100, write_only=True)
    district_name = serializers.CharField(max_length=100, write_only=True)
    subdistrict_name = serializers.CharField(max_length=100, write_only=True)
    zip_code = serializers.CharField(max_length=10, write_only=True)

    class Meta:
        model = ShippingAddress
        fields = [
            "province",
            "city",
            "district",
            "subdistrict",
            "user",
            "street_address",
            "province_name",
            "city_name",
            "district_name",
            "subdistrict_name",
            "zip_code",
            "latitude",
            "longitude",
            "is_default",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_user(self, obj):
        user = obj.user
        return {"id": user.id, "username": user.username, "email": user.email}

    def validate(self, attrs):
        prov_name = attrs.pop("province_name")
        city_name = attrs.pop("city_name")
        dist_name = attrs.pop("district_name")
        subd_name = attrs.pop("subdistrict_name")
        zip_code = attrs.pop("zip_code")

        if not re.fullmatch(r"\d+", zip_code):
            raise serializers.ValidationError({"zip_code": "Zip code must be digits."})

        try:
            province = Province.objects.get(name__iexact=prov_name)
        except Province.DoesNotExist:
            raise serializers.ValidationError({"province_name": "Province not found."})

        try:
            city = City.objects.get(name__iexact=city_name, province=province)
        except City.DoesNotExist:
            raise serializers.ValidationError({"city_name": "City not found."})

        try:
            district = District.objects.get(name__iexact=dist_name, city=city)
        except District.DoesNotExist:
            raise serializers.ValidationError({"district_name": "District not found."})

        try:
            subdistrict = SubDistrict.objects.get(
                name__iexact=subd_name, district=district, zip_code=zip_code
            )
        except SubDistrict.DoesNotExist:
            raise serializers.ValidationError(
                {"subdistrict_name": "Subdistrict not found."}
            )

        attrs["province"] = province
        attrs["city"] = city
        attrs["district"] = district
        attrs["subdistrict"] = subdistrict

        # jika new data atau update data bervalue is_default true
        # maka ambil data lama yang is_default true lalu ubah ke false
        if attrs["is_default"] == True:
            ship_addr = (
                ShippingAddress.objects.select_for_update()
                .filter(is_default=True, user=self.context["request"].user)
                .first()
            )
            if ship_addr:
                ship_addr.is_default = False
                ship_addr.save()

        return attrs

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


# class ShippingAddressListSerializer(serializers.ModelSerializer):
#     province = ProvinceSerializer(read_only=True)
#     city = CitySerializer(read_only=True)
#     district = DistrictSerializer(read_only=True)
#     subdistrict = SubDistrictSerializer(read_only=True)

#     class Meta:
#         model = ShippingAddress
#         fields = [
#             "id",
#             "province",
#             "city",
#             "district",
#             "subdistrict",
#             "street_address",
#             "created_at",
#             "updated_at",
#         ]
#         read_only_fields = fields
