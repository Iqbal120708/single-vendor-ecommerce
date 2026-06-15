from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model

# from rest_framework.test import APIClient
from django.core.exceptions import ValidationError

# from django.db import connection
# from django.test import TransactionTestCase
from django.urls import reverse
from freezegun import freeze_time
from rest_framework.test import APITestCase
from shipping_address.models import (
    City,
    District,
    Province,
    ShippingAddress,
    SubDistrict,
)

User = get_user_model()


@freeze_time("2025-12-08T11:45:00+07:00")
class TestAddress(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="test",
            email="test@gmail.com",
            password="test2938484jr",
            phone_number="089384442947",
        )
        EmailAddress.objects.create(
            user=cls.user, email=cls.user.email, verified=True, primary=True
        )

        cls.province = Province.objects.create(
            ro_id=1, name="NUSA TENGGARA BARAT (NTB)"
        )

        cls.city = City.objects.create(ro_id=1, name="MATARAM", province=cls.province)

        cls.district = District.objects.create(ro_id=1, name="MATARAM", city=cls.city)

        cls.subdistrict = SubDistrict.objects.create(
            ro_id=1, name="MATARAM", zip_code="12455", district=cls.district
        )

    def handle_login(self):
        login = self.client.post(
            reverse("rest_login"),
            {"email": self.user.email, "password": "test2938484jr"},
            format="json",
        )

        self.assertEqual(login.status_code, 200)

        token = login.data["access"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    @patch("accounts.signals.logger")
    def test_validate_serializer_zip_code(self, mock_logger):
        self.handle_login()

        res_post = self.client.post(
            reverse("shipping_address"),
            data={
                "province_name": "dj",
                "city_name": "hd",
                "district_name": "nd",
                "subdistrict_name": "nd",
                "zip_code": "djfjfj",
                "street_address": "nd",
            },
        )

        self.assertEqual(res_post.status_code, 400)

        data = res_post.data

        self.assertEqual(data["zip_code"][0], "Zip code must be digits.")

    @patch("accounts.signals.logger")
    def test_validate_serializer_province(self, mock_logger):
        self.handle_login()

        res_post = self.client.post(
            reverse("shipping_address"),
            data={
                "province_name": "fh",
                "city_name": "hd",
                "district_name": "nd",
                "subdistrict_name": "nd",
                "zip_code": "12455",
                "street_address": "nd",
            },
        )

        self.assertEqual(res_post.status_code, 400)

        data = res_post.data

        self.assertEqual(data["province_name"][0], "Province not found.")

    @patch("accounts.signals.logger")
    def test_validate_serializer_city(self, mock_logger):
        self.handle_login()

        res_post = self.client.post(
            reverse("shipping_address"),
            data={
                "province_name": "NUSA TENGGARA BARAT (NTB)",
                "city_name": "hd",
                "district_name": "nd",
                "subdistrict_name": "nd",
                "zip_code": "12455",
                "street_address": "nd",
            },
        )

        self.assertEqual(res_post.status_code, 400)

        data = res_post.data

        self.assertEqual(data["city_name"][0], "City not found.")

    @patch("accounts.signals.logger")
    def test_validate_serializer_district(self, mock_logger):
        self.handle_login()

        res_post = self.client.post(
            reverse("shipping_address"),
            data={
                "province_name": "NUSA TENGGARA BARAT (NTB)",
                "city_name": "MATARAM",
                "district_name": "nd",
                "subdistrict_name": "nd",
                "zip_code": "12455",
                "street_address": "nd",
            },
        )

        self.assertEqual(res_post.status_code, 400)

        data = res_post.data

        self.assertEqual(data["district_name"][0], "District not found.")

    @patch("accounts.signals.logger")
    def test_validate_serializer_subdistrict(self, mock_logger):
        self.handle_login()

        res_post = self.client.post(
            reverse("shipping_address"),
            data={
                "province_name": "NUSA TENGGARA BARAT (NTB)",
                "city_name": "MATARAM",
                "district_name": "MATARAM",
                "subdistrict_name": "nd",
                "zip_code": "12455",
                "street_address": "nd",
            },
        )

        self.assertEqual(res_post.status_code, 400)

        data = res_post.data

        self.assertEqual(data["subdistrict_name"][0], "Subdistrict not found.")

    @patch("accounts.signals.logger")
    def test_validate_model(self, mock_logger):
        province = Province.objects.create(name="test model", ro_id=2)
        city = City.objects.create(name="test model", province=province, ro_id=2)
        district = District.objects.create(name="test model", city=city, ro_id=2)
        subdistrict = SubDistrict.objects.create(
            name="test model", district=district, ro_id=2
        )

        with self.assertRaises(ValidationError) as ctx:
            shipping_address = ShippingAddress.objects.create(
                province=self.province,
                city=city,
                district=self.district,
                subdistrict=subdistrict,
                street_address="Jl. test model",
                user=self.user,
            )

            self.assertEqual(
                ctx["city"][0],
                "The selected city does not belong to the specified province.",
            )
            self.assertEqual(
                ctx["district"][0],
                "The selected district does not belong to the specified city.",
            )
            self.assertEqual(
                ctx["subdistrict"][0],
                "The selected subdistrict does not belong to the specified district.",
            )
