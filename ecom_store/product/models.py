from django.db import models

from config.models import BaseModel


class Category(BaseModel):
    name = models.CharField(max_length=255)
    desc = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class Product(BaseModel):
    name = models.CharField(max_length=255)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, related_name="products", null=True
    )
    variant_name = models.CharField(max_length=255)
    weight = models.PositiveIntegerField(help_text="Product weight in grams")
    width = models.PositiveIntegerField(help_text="Product width in cm")
    height = models.PositiveIntegerField(help_text="Product height in cm")
    length = models.PositiveIntegerField(help_text="Product length in cm")
    stock = models.PositiveIntegerField()
    reserved_stock = models.PositiveIntegerField(default=0, blank=True)
    price = models.DecimalField(max_digits=18, decimal_places=2)

    def __str__(self):
        return self.name
