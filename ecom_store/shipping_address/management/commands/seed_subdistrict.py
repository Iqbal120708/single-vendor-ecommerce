import random

import requests as req
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from shipping_address.models import City, District, Province, SubDistrict

User = get_user_model()


class Command(BaseCommand):
    help = "Generate data subdistrict use data RajaOngkir"

    def handle(self, *args, **kwargs):
        headers = {"Key": settings.API_KEY_RAJA_ONGKIR_SHIPPING_COST}

        subdistrict_data = SubDistrict.objects.values_list(
            "district__ro_id", flat=True
        ).distinct()
        districts = District.objects.all()

        if subdistrict_data:
            districts = districts.exclude(ro_id__in=subdistrict_data)

        for district in districts:
            subdistrict_req = req.get(
                f"https://rajaongkir.komerce.id/api/v1/destination/sub-district/{district.ro_id}",
                headers=headers,
            )

            if subdistrict_req.status_code == 429:
                self.stdout.write(
                    self.style.WARNING(f"API limit in district ro_id {district.ro_id}")
                )
                return

            if not subdistrict_req.json()["data"]:
                self.stdout.write(
                    self.style.WARNING(
                        f"district ro_id {district.ro_id} do not have data"
                    )
                )
                continue

            for data in subdistrict_req.json()["data"]:
                subdistrict, _ = SubDistrict.objects.get_or_create(
                    ro_id=data["id"],
                    name=data["name"],
                    zip_code=data["zip_code"],
                    district=district,
                )

        self.stdout.write(self.style.SUCCESS("data subdistrict created"))
