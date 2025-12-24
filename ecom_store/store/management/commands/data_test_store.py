# import random
#from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from allauth.account.models import EmailAddress
from shipping_address.models import Province, City, District, SubDistrict, ShippingAddress
from store.models import Store

User = get_user_model()


class Command(BaseCommand):
    help = "Generate data store for test case"

    def handle(self, *args, **kwargs):
        # 1. Membuat Superuser
        self.superuser = User.objects.create_superuser(
            username="admin_test",
            email="admin@example.com",
            password="adminpassword123",
            phone_number="081234567890",
        )
        
        EmailAddress.objects.create(
            user=self.superuser, 
            email=self.superuser.email, 
            verified=True, 
            primary=True
        )
        
        # 2. Membuat Data Wilayah Baru (ro_id=2)
        self.province_2 = Province.objects.create(
            ro_id=2,
            name='JAWA BARAT'
        )
        
        self.city_2 = City.objects.create(
            ro_id=2,
            name='BANDUNG',
            province=self.province_2
        )
        
        self.district_2 = District.objects.create(
            ro_id=2,
            name='COBLONG',
            city=self.city_2
        )
        
        self.subdistrict_2 = SubDistrict.objects.create(
            ro_id=2,
            name='DAGO',
            zip_code='40135',
            district=self.district_2
        )
        
        # 3. Membuat Shipping Address Kedua (untuk superuser)
        self.shipping_address_2 = ShippingAddress.objects.create(
            province=self.province_2,
            city=self.city_2,
            district=self.district_2,
            subdistrict=self.subdistrict_2,
            street_address="Jl. Dago No. 123",
            is_default=True,
            user=self.superuser
        )
        
        self.store = Store.objects.create(
            brand_name="Store Test",
            name="Store",
            email="store@gmail.com",
            phone_number="080987654321",
            shipping_address=self.shipping_address_2,
        )
        

        self.stdout.write(self.style.SUCCESS("store data test created"))
        
