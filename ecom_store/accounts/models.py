import warnings

from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from phonenumber_field.modelfields import PhoneNumberField


class UserDeleteWarning(Warning):
    pass


class CustomUserQuerySet(models.QuerySet):
    def delete(self):
        raise RuntimeError("Gunakan soft_delete() atau hard_delete() per instance")

    def soft_delete(self):
        return self.update(is_active=False)

    def hard_delete(self):
        return super().delete()


class CustomUserManager(BaseUserManager):
    def get_queryset(self):
        return CustomUserQuerySet(self.model, using=self._db)

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        user = self.create_user(email, password, **extra_fields)

        # auto-verify email for superuser via allauth
        from allauth.account.models import EmailAddress

        EmailAddress.objects.update_or_create(
            user=user,
            email=user.email,
            defaults={"verified": True, "primary": True},
        )

        return user


class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    phone_number = PhoneNumberField(unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

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
