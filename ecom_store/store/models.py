from django.core.exceptions import ValidationError
from django.db import models
from phonenumber_field.modelfields import PhoneNumberField

from config.models import BaseModel
from shipping_address.models import ShippingAddress


# Create your models here.
class Store(BaseModel):
    brand_name = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone_number = PhoneNumberField(unique=True)
    shipping_address = models.ForeignKey(ShippingAddress, on_delete=models.PROTECT)
    is_active = models.BooleanField(default=True)

    @property
    def clean_phone_number(self):
        if self.phone_number:
            return str(self.phone_number).replace("+", "")
        return ""
        
    def clean(self):
        if not self.shipping_address.user.is_superuser:
            raise ValidationError(
                "Alamat pengiriman toko harus dimiliki oleh akun superuser."
            )

    def save(self, *args, **kwargs):
        self.clean()
        if self.is_active:
            Store.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(
            "Data toko tidak dapat dihapus. Silakan nonaktifkan toko dengan mengubah status aktif."
        )
