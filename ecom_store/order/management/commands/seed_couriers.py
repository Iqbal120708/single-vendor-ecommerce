import random
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from order.models import Courier

User = get_user_model()


class Command(BaseCommand):
    help = "Generate data couriers"

    def handle(self, *args, **kwargs):
        couriers = [
            {"code": "jne", "name": "Jalur Nugraha Ekakurir (JNE)"},
            {"code": "jnt", "name": "J&T Express"},
            {"code": "sicepat", "name": "SiCepat Express"},
            {"code": "tiki", "name": "TIKI"},
            {"code": "pos", "name": "POS Indonesia (POS)"},
            {"code": "ninja", "name": "Ninja Xpress"},
            {"code": "ide", "name": "ID Express"},
        ]

        for courier in couriers:
            Courier.objects.create(name=courier["name"], code=courier["code"])

        self.stdout.write(self.style.SUCCESS("data couriers created"))
