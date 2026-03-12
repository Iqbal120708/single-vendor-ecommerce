import random

import requests as req
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from shipping_address.models import Province

User = get_user_model()


class Command(BaseCommand):
    help = "Generate data province use data RajaOngkir"

    def handle(self, *args, **kwargs):
        headers = {"Key": settings.API_KEY_RAJA_ONGKIR_SHIPPING_COST}
        province_req = req.get(
            "https://rajaongkir.komerce.id/api/v1/destination/province", headers=headers
        )

        for data in province_req.json()["data"]:
            province, _ = Province.objects.get_or_create(
                ro_id=data["id"], name=data["name"]
            )

        self.stdout.write(self.style.SUCCESS("data province created"))
