from django.core.management.base import BaseCommand
from product.models import Product, Category
from django.contrib.auth import get_user_model
import random
from decimal import Decimal

User = get_user_model()

class Command(BaseCommand):
    help = "Generate 10 sample products"

    def handle(self, *args, **kwargs):
        # pastikan ada kategori
        category, _ = Category.objects.get_or_create(
            name="Default Category",
            defaults={"desc": "Sample category"}
        )
            
        for i in range(1, 11):
            Product.objects.create(
                name=f"Sample Product {i}",
                price=random.randint(10000, 200000),
                category=category,
                stock=50,
                weight=Decimal(str(round(random.uniform(0.1, 10.0), 2)))
            )

        self.stdout.write(self.style.SUCCESS("10 sample products created"))