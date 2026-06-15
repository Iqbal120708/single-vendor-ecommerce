from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework.test import APITestCase
from shipping_address.models import (
    City,
    District,
    Province,
    ShippingAddress,
    SubDistrict,
)
from store.models import Store

User = get_user_model()


# Create your tests here.
class StoreTest(APITestCase):
    @classmethod
    def setUpTestData(self):
        # 1. Membuat Superuser
        self.superuser = User.objects.create_superuser(
            username="admin_test",
            email="admin@example.com",
            password="adminpassword113",
            phone_number="081134567890",
        )

        EmailAddress.objects.create(
            user=self.superuser, email=self.superuser.email, verified=True, primary=True
        )

        # 2. Membuat Data Wilayah Baru (ro_id=1)
        self.province = Province.objects.create(ro_id=1, name="JAWA BARAT")

        self.city = City.objects.create(ro_id=1, name="BANDUNG", province=self.province)

        self.district = District.objects.create(ro_id=1, name="COBLONG", city=self.city)

        self.subdistrict = SubDistrict.objects.create(
            ro_id=1, name="DAGO", zip_code="40135", district=self.district
        )

        # 3. Membuat Shipping Address Kedua (untuk superuser)
        self.shipping_address = ShippingAddress.objects.create(
            province=self.province,
            city=self.city,
            district=self.district,
            subdistrict=self.subdistrict,
            street_address="Jl. Dago No. 113",
            is_default=True,
            user=self.superuser,
        )

        self.store = Store.objects.create(
            brand_name="Store Test",
            name="Store",
            email="store@gmail.com",
            phone_number="080987654311",
            shipping_address=self.shipping_address,
        )

    @patch("accounts.signals.logger")
    def test_delete(self, mock_logger):
        with self.assertRaises(ValidationError) as ctx:
            self.store.delete()
            self.assertEqual(
                ctx,
                "Data toko tidak dapat dihapus. Silakan nonaktifkan toko dengan mengubah status aktif.",
            )
