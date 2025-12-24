#import random
#from decimal import Decimal

from django.contrib.auth import get_user_model
from allauth.account.models import EmailAddress
from django.core.management.base import BaseCommand
from shipping_address.models import Province, City, District, SubDistrict, ShippingAddress

User = get_user_model()


class Command(BaseCommand):
    help = "Generate data user for test case"

    def handle(self, *args, **kwargs):
        self.user = User.objects.create_user(
            username="test",
            email="test@gmail.com",
            password="test2938484jr",
            phone_number="089384442947",
        )
        EmailAddress.objects.create(
            user=self.user, email=self.user.email, verified=True, primary=True
        )

        self.province = Province.objects.create(
            ro_id=1,
            name='NUSA TENGGARA BARAT (NTB)'
        )
        
        self.city = City.objects.create(
            ro_id=1,
            name='MATARAM',
            province=self.province
        )
        
        self.district = District.objects.create(
            ro_id=1,
            name='MATARAM',
            city=self.city
        )
        
        self.subdistrict = SubDistrict.objects.create(
            ro_id=1,
            name='MATARAM',
            zip_code='12455',
            district=self.district
        )
        
        self.shipping_address = ShippingAddress.objects.create(
            province=self.province,
            city=self.city,
            district=self.district,
            subdistrict=self.subdistrict,
            street_address="Jl. Test",
            is_default=True,
            user=self.user
        )

        self.stdout.write(self.style.SUCCESS("user data test created"))
