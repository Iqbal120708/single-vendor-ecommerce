from config.models import BaseModel
from django.contrib.auth import get_user_model
from django.db import models
from product.models import Product

User = get_user_model()

# Create your models here.
class Cart(BaseModel):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="carts"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="cart_items"
    )
    qty = models.PositiveIntegerField(default=1)
    
    class Meta:
        unique_together = (
            'user', 
            'product', 
        )

    def __str__(self):
        return f"{self.user} - {self.product} ({self.qty})"