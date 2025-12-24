import warnings

from django.contrib.auth.models import AbstractUser
from django.db import models
from phonenumber_field.modelfields import PhoneNumberField

from django.conf import settings
class UserDeleteWarning(Warning):
    pass


class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    phone_number = PhoneNumberField(unique=True)
    pending_delete = models.BooleanField(default=False)
    #     shipping_addresses = models.ManyToManyField(
    #     "shipping_address.ShippingAddress",
    #     through="UserShippingAddress",
    #     related_name="users",
    #     blank=True
    # )
    
    @property
    def clean_phone_number(self):
        if self.phone_number:
            return str(self.phone_number).replace('+', '')
        return ""

    def delete(self, *args, **kwargs):
        if not self.pending_delete:
            warnings.warn(
                "method delete() di model User dipanggil! Gunakan method soft_delete() untuk delete. Lakukan penghapusan ulang jika tetap ingin menghapus",
                category=UserDeleteWarning,
                stacklevel=2,
            )
            self.pending_delete = True
            super().save(*args, **kwargs)
        else:
            return super().delete(*args, **kwargs)

    def soft_delete(self, *args, **kwargs):
        self.is_active = False
        self.save()
        
# from django.db.models import Q

# class UserShippingAddress(models.Model):
#     user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
#     address = models.ForeignKey(ShippingAddress, on_delete=models.CASCADE)
#     is_default = models.BooleanField(default=False)

    # class Meta:
    #     constraints = [
    #         models.UniqueConstraint(
    #             fields=["user"],
    #             condition=Q(is_default=True),
    #             name="unique_default_address_per_user",
    #         )
    #     ]
