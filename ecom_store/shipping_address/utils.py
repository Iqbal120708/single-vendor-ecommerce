# def format_address(shipping_address):
#     street = shipping_address.street_address
#     kecamatan = shipping_address.subdistrict.name
#     kota_kab = shipping_address.city.name
#     kode_pos = shipping_address.subdistrict.zip_code

#     address_parts = [
#         street,
#         f"Kec. {kecamatan}",
#         kota_kab,
#         kode_pos
#     ]

#     # Filter jika ada data yang None/Kosong agar tidak muncul koma berlebih
#     return ", ".join([str(p) for p in address_parts if p])

import requests
from django.conf import settings
from rest_framework import serializers


def get_destination_id(serializer_data):
    headers = {"x-api-key": settings.API_KEY_RAJA_ONGKIR_SHIPPING_DELIVERY}

    url = (
        "https://api-sandbox.collaborator.komerce.id"
        "/tariff/api/v1/destination/search"
    )

    params = {"keyword": serializer_data["subdistrict"].zip_code}

    res = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=10,
    )

    data = res.json()

    if res.status_code != 200:
        raise serializers.ValidationError({"error": data["meta"]["message"]})

    matches = [
        item
        for item in data["data"]
        if (
            item["subdistrict_name"].upper()
            == serializer_data["subdistrict"].name.upper()
            and item["district_name"].upper()
            == serializer_data["district"].name.upper()
            and item["city_name"].upper() == serializer_data["city"].name.upper()
            and item["zip_code"] == serializer_data["subdistrict"].zip_code
        )
    ]

    if not matches:
        raise serializers.ValidationError(
            {"destination": ("Destination RajaOngkir tidak ditemukan.")}
        )

    if len(matches) > 1:
        raise serializers.ValidationError(
            {"destination": ("Ditemukan lebih dari satu destination yang cocok.")}
        )

    return matches[0]["id"]
