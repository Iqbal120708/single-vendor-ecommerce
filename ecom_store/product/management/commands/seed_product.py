import random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from product.models import Category, Product

# from decimal import Decimal


User = get_user_model()


class Command(BaseCommand):
    help = "Generate 10 sample products"

    def handle(self, *args, **kwargs):
        # pastikan ada kategori
        category, _ = Category.objects.get_or_create(
            name="Default Category", defaults={"desc": "Sample category"}
        )

        for i in range(1, 11):
            Product.objects.create(
                variant_name=f"Variant Sample Product {i}",
                name=f"Sample Product {i}",
                price=10_000*i,
                category=category,
                stock=50,
                weight=500*i,
                height=2+i,
                width=2+i,
                length=5*i,
            )

        self.stdout.write(self.style.SUCCESS("10 sample products created"))
