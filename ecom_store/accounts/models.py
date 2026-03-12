import warnings

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from phonenumber_field.modelfields import PhoneNumberField


class UserDeleteWarning(Warning):
    pass


class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    phone_number = PhoneNumberField(unique=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    @property
    def clean_phone_number(self):
        if self.phone_number:
            return str(self.phone_number).replace("+", "")
        return ""

    def soft_delete(self):
        self.is_active = False
        self.save(update_fields=["is_active"])
    
    def hard_delete(self):
        return super().delete()
    
    def delete(self, *args, **kwargs):
        raise RuntimeError("Gunakan soft_delete() atau hard_delete()")

    def __str__(self):
        return self.email
        
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
