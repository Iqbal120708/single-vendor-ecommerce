from config.models import BaseModel
from django.db import models

class Category(BaseModel):
    name = models.CharField(max_length=255)
    desc = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class Product(BaseModel):
    name = models.CharField(max_length=255)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        related_name="products",
        null=True
    )
    weight = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=18, decimal_places=2)

    def __str__(self):
        return self.name


