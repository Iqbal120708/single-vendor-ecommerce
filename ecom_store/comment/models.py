from django.db import models
from config.models import BaseModel
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils import timezone
from datetime import timedelta

# Create your models here.

class Comment(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    product = models.ForeignKey("product.Product", on_delete=models.CASCADE)
    content = models.TextField()
    rating = models.PositiveIntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(5)
        ]    
    )
    is_archived = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ("user", "product")
        
    def is_editable(self):
        batas_waktu = self.created_at + timedelta(hours=24)
        return timezone.now() <= batas_waktu