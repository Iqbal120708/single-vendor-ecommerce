import random

import requests as req
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from shipping_address.models import City, Province

User = get_user_model()


class Command(BaseCommand):
    help = "Generate data city use data RajaOngkir"

    def handle(self, *args, **kwargs):
        headers = {"Key": settings.API_KEY_RAJA_ONGKIR_SHIPPING_COST}

        city_data = City.objects.values_list("province__ro_id", flat=True).distinct()
        provinces = Province.objects.all()

        if city_data:
            provinces = provinces.exclude(ro_id__in=city_data)

        for province in provinces:
            city_req = req.get(
                f"https://rajaongkir.komerce.id/api/v1/destination/city/{province.ro_id}",
                headers=headers,
            )

            for data in city_req.json()["data"]:
                city, _ = City.objects.get_or_create(
                    ro_id=data["id"],
                    name=data["name"],
                    province=province,
                )

        self.stdout.write(self.style.SUCCESS("data city created"))
