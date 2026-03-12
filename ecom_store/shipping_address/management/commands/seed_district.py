import random

import requests as req
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from shipping_address.models import City, District, Province

User = get_user_model()


class Command(BaseCommand):
    help = "Generate data district use data RajaOngkir"

    def handle(self, *args, **kwargs):
        headers = {"Key": settings.API_KEY_RAJA_ONGKIR_SHIPPING_COST}

        district_data = District.objects.values_list(
            "city__ro_id", flat=True
        ).distinct()
        cities = City.objects.all()

        if district_data:
            cities = cities.exclude(ro_id__in=district_data)

        for city in cities:
            district_req = req.get(
                f"https://rajaongkir.komerce.id/api/v1/destination/district/{city.ro_id}",
                headers=headers,
            )

            if district_req.status_code == 429:
                self.stdout.write(
                    self.style.WARNING(f"API limit in city ro_id {city.ro_id}")
                )
                return

            if not district_req.json()["data"]:
                self.stdout.write(
                    self.style.WARNING(f"city ro_id {city.ro_id} do not have data")
                )
                continue

            for data in district_req.json()["data"]:
                district, _ = District.objects.get_or_create(
                    ro_id=data["id"],
                    name=data["name"],
                    city=city,
                )

        self.stdout.write(self.style.SUCCESS("data district created"))
