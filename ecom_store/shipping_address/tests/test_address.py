from unittest.mock import patch
#from rest_framework.test import APITestCase
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase
from django.urls import reverse
#from freezegun import freeze_time
from rest_framework.test import APIClient

from shipping_address.models import Province, City, District, SubDistrict

User = get_user_model()

class TestAddress(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.client = APIClient()

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
    def test_get_province(self, mock_logger):
        self.handle_login()
        res_get = self.client.get(reverse("province"))
        self.assertEqual(res_get.status_code, 200)

        self.assertEqual(len(res_get.data), 1)
    
        data = res_get.data[0]
        self.assertEqual(data["ro_id"], 1)
        self.assertEqual(data["name"], "NUSA TENGGARA BARAT (NTB)")
        
    @patch("accounts.signals.logger")
    def test_get_city(self, mock_logger):
        self.handle_login()
        res_get = self.client.get(reverse("city"))
        self.assertEqual(res_get.status_code, 200)

        self.assertEqual(len(res_get.data), 1)
    
        data = res_get.data[0]
        self.assertEqual(data["ro_id"], 1)
        self.assertEqual(data["name"], "MATARAM")
        
        self.assertEqual(data["province"]["ro_id"], 1)
        self.assertEqual(data["province"]["name"], "NUSA TENGGARA BARAT (NTB)")
        
    @patch("accounts.signals.logger")
    def test_get_district(self, mock_logger):
        self.handle_login()
        res_get = self.client.get(reverse("district"))
        self.assertEqual(res_get.status_code, 200)

        self.assertEqual(len(res_get.data), 1)
    
        data = res_get.data[0]
        self.assertEqual(data["ro_id"], 1)
        self.assertEqual(data["name"], "MATARAM")
        
        self.assertEqual(data["city"]["ro_id"], 1)
        self.assertEqual(data["city"]["name"], "MATARAM")
        
    @patch("accounts.signals.logger")
    def test_get_subdistrict(self, mock_logger):
        self.handle_login()
        res_get = self.client.get(reverse("subdistrict"))
        self.assertEqual(res_get.status_code, 200)

        self.assertEqual(len(res_get.data), 1)
    
        data = res_get.data[0]
        self.assertEqual(data["ro_id"], 1)
        self.assertEqual(data["name"], "MATARAM")
        self.assertEqual(data["zip_code"], "12455")
        
        self.assertEqual(data["district"]["ro_id"], 1)
        self.assertEqual(data["district"]["name"], "MATARAM")
        
    @patch("accounts.signals.logger")
    def test_get_province_with_pk(self, mock_logger):
        self.handle_login()
        res_get = self.client.get(reverse("province", args=[1]))
        self.assertEqual(res_get.status_code, 200)
    
        data = res_get.data
        self.assertEqual(data["ro_id"], 1)
        self.assertEqual(data["name"], "NUSA TENGGARA BARAT (NTB)")
        
    @patch("accounts.signals.logger")
    def test_get_city_with_pk(self, mock_logger):
        self.handle_login()
        res_get = self.client.get(reverse("city", args=[1]))
        self.assertEqual(res_get.status_code, 200)
    
        data = res_get.data
        self.assertEqual(data["ro_id"], 1)
        self.assertEqual(data["name"], "MATARAM")
        
        self.assertEqual(data["province"]["ro_id"], 1)
        self.assertEqual(data["province"]["name"], "NUSA TENGGARA BARAT (NTB)")
        
    @patch("accounts.signals.logger")
    def test_get_district_with_pk(self, mock_logger):
        self.handle_login()
        res_get = self.client.get(reverse("district", args=[1]))
        self.assertEqual(res_get.status_code, 200)
    
        data = res_get.data
        self.assertEqual(data["ro_id"], 1)
        self.assertEqual(data["name"], "MATARAM")
        
        self.assertEqual(data["city"]["ro_id"], 1)
        self.assertEqual(data["city"]["name"], "MATARAM")
        
    @patch("accounts.signals.logger")
    def test_get_subdistrict_with_pk(self, mock_logger):
        self.handle_login()
        res_get = self.client.get(reverse("subdistrict", args=[1]))
        self.assertEqual(res_get.status_code, 200)
    
        data = res_get.data
        self.assertEqual(data["ro_id"], 1)
        self.assertEqual(data["name"], "MATARAM")
        self.assertEqual(data["zip_code"], "12455")
        
        self.assertEqual(data["district"]["ro_id"], 1)
        self.assertEqual(data["district"]["name"], "MATARAM")