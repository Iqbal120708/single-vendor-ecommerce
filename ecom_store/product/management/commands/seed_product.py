import random
#from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from product.models import Category, Product

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
                price=random.randint(10000, 200000),
                category=category,
                stock=50,
                weight=random.randint(500, 1000),
                height=random.randint(2,8),
                width=random.randint(2,10),
                length=random.randint(5, 50)
            )

        self.stdout.write(self.style.SUCCESS("10 sample products created"))
