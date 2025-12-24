from django.db import models
from django.db.models import Q
from config.models import BaseModel
from django.conf import settings
from django.core.exceptions import ValidationError

class Province(BaseModel):
    ro_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=100)


class City(BaseModel):
    ro_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=100)
    province = models.ForeignKey(Province, on_delete=models.CASCADE)


class District(BaseModel):
    ro_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=100)
    city = models.ForeignKey(City, on_delete=models.CASCADE)


class SubDistrict(BaseModel):
    ro_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=100)
    district = models.ForeignKey(District, on_delete=models.CASCADE)
    zip_code = models.CharField(max_length=10)

class ShippingAddress(BaseModel):
    province = models.ForeignKey(Province, on_delete=models.PROTECT)
    city = models.ForeignKey(City, on_delete=models.PROTECT)
    district = models.ForeignKey(District, on_delete=models.PROTECT)
    subdistrict = models.ForeignKey(SubDistrict, on_delete=models.PROTECT)
    street_address = models.CharField(max_length=255)
    is_default = models.BooleanField(default=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    
    def clean(self):
        errors = {}
        
        if self.city.province != self.province:
            errors["city"] = (
                "The selected city does not belong to the specified province."
            )

        if self.district.city != self.city:
            errors["district"] = (
                "The selected district does not belong to the specified city."
            )

        if self.subdistrict.district != self.district:
            errors["subdistrict"] = (
                "The selected subdistrict does not belong to the specified district."
            )

        if errors:
            raise ValidationError(errors)

    @property
    def formatted_address(self):
        street = self.street_address
        kecamatan = self.subdistrict.name
        kota_kab = self.city.name
        kode_pos = self.subdistrict.zip_code
    
        address_parts = [
            street,
            f"Kec. {kecamatan}",
            kota_kab,
            kode_pos
        ]
        
        # Filter jika ada data yang None/Kosong agar tidak muncul koma berlebih
        return ", ".join([str(p) for p in address_parts if p])
        
    class Meta:
        # unique_together = (
        #     "province",
        #     "city",
        #     "district",
        #     "subdistrict",
        #     "street_address",
        # )
        
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(is_default=True),
                name="unique_default_address_per_user",
            )
        ]

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


# shi_add = ShippingAddress.objects.filter(
#     province__name__iexact="",
#     city__name__iexact="",
#     district__name__iexact="",
#     subdistrict__name__iexact="",
#     subdistrict__zip_code="",
#     street_address__iexact=""
# ).first()

# if not shi_add:
#     ShippingAddress.objects.create(
#         province__name__iexact="",
#         city__name__iexact="",
#         district__name__iexact="",
#         subdistrict__name__iexact="",
#         subdistrict__zip_code__iexact="",
#         street_address__iexact=""
#     )
