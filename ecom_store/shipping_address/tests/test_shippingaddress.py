from unittest.mock import patch

# from rest_framework.test import APITestCase
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
# from django.db import connection
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from freezegun import freeze_time
from rest_framework.test import APIClient

from shipping_address.models import (City, District, Province, ShippingAddress,
                                     SubDistrict)

User = get_user_model()


@override_settings(USE_TZ=True)
@freeze_time("2025-12-08T11:45:00+07:00")
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

        self.user2 = User.objects.create_user(
            username="test2",
            email="test2@gmail.com",
            password="test2938484jr",
            phone_number="089384742947",
        )
        EmailAddress.objects.create(
            user=self.user2, email=self.user2.email, verified=True, primary=True
        )

        self.province = Province.objects.create(
            ro_id=1, name="NUSA TENGGARA BARAT (NTB)"
        )

        self.city = City.objects.create(ro_id=1, name="MATARAM", province=self.province)

        self.district = District.objects.create(ro_id=1, name="MATARAM", city=self.city)

        self.subdistrict = SubDistrict.objects.create(
            ro_id=1, name="MATARAM", zip_code="12455", district=self.district
        )

        self.shipping_address = ShippingAddress.objects.create(
            province=self.province,
            city=self.city,
            district=self.district,
            subdistrict=self.subdistrict,
            street_address="Jl. Test",
            is_default=True,
            user=self.user,
        )

        self.shipping_address2 = ShippingAddress.objects.create(
            province=self.province,
            city=self.city,
            district=self.district,
            subdistrict=self.subdistrict,
            street_address="Jl. Test 2",
            is_default=True,
            user=self.user2,
        )

        self.shipping_address3 = ShippingAddress.objects.create(
            province=self.province,
            city=self.city,
            district=self.district,
            subdistrict=self.subdistrict,
            street_address="Jl. Test 3",
            user=self.user2,
        )

    def handle_login(self, user=None):
        if not user:
            user = self.user

        login = self.client.post(
            reverse("rest_login"),
            {"email": user.email, "password": "test2938484jr"},
            format="json",
        )

        self.assertEqual(login.status_code, 200)

        token = login.data["access"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    @patch("accounts.signals.logger")
    def test_get_with_user1(self, mock_logger):
        self.handle_login()

        res = self.client.get(reverse("shipping_address"))

        self.assertEqual(len(res.data), 1)

        data = res.data[0]
        self.assertEqual(data["province"]["ro_id"], 1)
        self.assertEqual(data["province"]["name"], "NUSA TENGGARA BARAT (NTB)")

        self.assertEqual(data["city"]["ro_id"], 1)
        self.assertEqual(data["city"]["name"], "MATARAM")

        self.assertEqual(data["district"]["ro_id"], 1)
        self.assertEqual(data["district"]["name"], "MATARAM")

        self.assertEqual(data["subdistrict"]["ro_id"], 1)
        self.assertEqual(data["subdistrict"]["name"], "MATARAM")
        self.assertEqual(data["subdistrict"]["zip_code"], "12455")

        self.assertEqual(data["street_address"], "Jl. Test")
        self.assertEqual(data["created_at"], "2025-12-08T11:45:00+07:00")
        self.assertEqual(data["updated_at"], "2025-12-08T11:45:00+07:00")
        self.assertTrue(data["is_default"])

        self.assertEqual(data["user"]["id"], 1)
        self.assertEqual(data["user"]["username"], "test")
        self.assertEqual(data["user"]["email"], "test@gmail.com")

    @patch("accounts.signals.logger")
    def test_get_with_user2(self, mock_logger):
        self.handle_login(self.user2)

        res = self.client.get(reverse("shipping_address"))

        self.assertEqual(len(res.data), 2)

        data = res.data[0]
        self.assertEqual(data["province"]["ro_id"], 1)
        self.assertEqual(data["province"]["name"], "NUSA TENGGARA BARAT (NTB)")

        self.assertEqual(data["city"]["ro_id"], 1)
        self.assertEqual(data["city"]["name"], "MATARAM")

        self.assertEqual(data["district"]["ro_id"], 1)
        self.assertEqual(data["district"]["name"], "MATARAM")

        self.assertEqual(data["subdistrict"]["ro_id"], 1)
        self.assertEqual(data["subdistrict"]["name"], "MATARAM")
        self.assertEqual(data["subdistrict"]["zip_code"], "12455")

        self.assertEqual(data["street_address"], "Jl. Test 2")
        self.assertEqual(data["created_at"], "2025-12-08T11:45:00+07:00")
        self.assertEqual(data["updated_at"], "2025-12-08T11:45:00+07:00")
        self.assertTrue(data["is_default"])

        self.assertEqual(data["user"]["id"], 2)
        self.assertEqual(data["user"]["username"], "test2")
        self.assertEqual(data["user"]["email"], "test2@gmail.com")

        data2 = res.data[1]
        self.assertEqual(data2["province"]["ro_id"], 1)
        self.assertEqual(data2["province"]["name"], "NUSA TENGGARA BARAT (NTB)")

        self.assertEqual(data2["city"]["ro_id"], 1)
        self.assertEqual(data2["city"]["name"], "MATARAM")

        self.assertEqual(data2["district"]["ro_id"], 1)
        self.assertEqual(data2["district"]["name"], "MATARAM")

        self.assertEqual(data2["subdistrict"]["ro_id"], 1)
        self.assertEqual(data2["subdistrict"]["name"], "MATARAM")
        self.assertEqual(data2["subdistrict"]["zip_code"], "12455")

        self.assertEqual(data2["street_address"], "Jl. Test 3")
        self.assertEqual(data2["created_at"], "2025-12-08T11:45:00+07:00")
        self.assertEqual(data2["updated_at"], "2025-12-08T11:45:00+07:00")
        self.assertFalse(data2["is_default"])

        self.assertEqual(data2["user"]["id"], 2)
        self.assertEqual(data2["user"]["username"], "test2")
        self.assertEqual(data2["user"]["email"], "test2@gmail.com")

    @patch("accounts.signals.logger")
    def test_get_with_pk(self, mock_logger):
        self.handle_login()

        res = self.client.get(reverse("shipping_address", args=[1]))

        data = res.data
        self.assertEqual(data["province"]["ro_id"], 1)
        self.assertEqual(data["province"]["name"], "NUSA TENGGARA BARAT (NTB)")

        self.assertEqual(data["city"]["ro_id"], 1)
        self.assertEqual(data["city"]["name"], "MATARAM")

        self.assertEqual(data["district"]["ro_id"], 1)
        self.assertEqual(data["district"]["name"], "MATARAM")

        self.assertEqual(data["subdistrict"]["ro_id"], 1)
        self.assertEqual(data["subdistrict"]["name"], "MATARAM")
        self.assertEqual(data["subdistrict"]["zip_code"], "12455")

        self.assertEqual(data["street_address"], "Jl. Test")
        self.assertEqual(data["created_at"], "2025-12-08T11:45:00+07:00")
        self.assertEqual(data["updated_at"], "2025-12-08T11:45:00+07:00")
        self.assertTrue(data["is_default"])

        self.assertEqual(data["user"]["id"], 1)
        self.assertEqual(data["user"]["username"], "test")
        self.assertEqual(data["user"]["email"], "test@gmail.com")

    @patch("accounts.signals.logger")
    def test_get_with_pk_but_not_have_user(self, mock_logger):
        """
        This test gets data with pk but the data is not his
        """
        self.handle_login()

        res = self.client.get(reverse("shipping_address", args=[2]))

        data = res.data
        self.assertEqual(data, {})

    @patch("accounts.signals.logger")
    def test_post_new_data(self, mock_logger):
        """
        This test adds new data because it is different from existing data
        """
        self.handle_login()
        res_post = self.client.post(
            reverse("shipping_address"),
            data={
                "province_name": "NUSA TENGGARA BARAT (NTB)",
                "city_name": "MATARAM",
                "district_name": "MATARAM",
                "subdistrict_name": "MATARAM",
                "zip_code": "12455",
                "street_address": "Jl. Post",
                "is_default": True,
            },
        )

        self.assertEqual(res_post.status_code, 201)

        res = self.client.get(reverse("shipping_address"))

        self.assertEqual(len(res.data), 2)

        data = res.data[1]
        self.assertEqual(data["province"]["ro_id"], 1)
        self.assertEqual(data["province"]["name"], "NUSA TENGGARA BARAT (NTB)")

        self.assertEqual(data["city"]["ro_id"], 1)
        self.assertEqual(data["city"]["name"], "MATARAM")

        self.assertEqual(data["district"]["ro_id"], 1)
        self.assertEqual(data["district"]["name"], "MATARAM")

        self.assertEqual(data["subdistrict"]["ro_id"], 1)
        self.assertEqual(data["subdistrict"]["name"], "MATARAM")
        self.assertEqual(data["subdistrict"]["zip_code"], "12455")

        self.assertEqual(data["street_address"], "Jl. Post")
        self.assertEqual(data["created_at"], "2025-12-08T11:45:00+07:00")
        self.assertEqual(data["updated_at"], "2025-12-08T11:45:00+07:00")
        self.assertTrue(data["is_default"])

        self.assertEqual(data["user"]["id"], 1)
        self.assertEqual(data["user"]["username"], "test")
        self.assertEqual(data["user"]["email"], "test@gmail.com")

        # mengecek data is_default true sebelumnya
        # data field is_default menjadi False
        self.assertTrue(self.shipping_address.is_default)
        self.shipping_address.refresh_from_db()
        self.assertFalse(self.shipping_address.is_default)

        # mengecek data yang is_default true hanya ada 1
        self.assertEqual(
            len(ShippingAddress.objects.filter(is_default=True, user=self.user)), 1
        )

        # mengecek data di buat
        # data ada 4, 3 dari setup, 1 dari post
        shipping_address = ShippingAddress.objects.all()
        self.assertEqual(len(shipping_address), 4)

    # @patch("accounts.signals.logger")
    # def test_post_old_data(self, mock_logger):
    #     """
    #     This test retrive old data because it is same from existing data
    #     """
    #     self.handle_login()
    #     res_post = self.client.post(reverse("shipping_address"), data={
    #         "province_name": "NUSA TENGGARA BARAT (NTB)",
    #         "city_name": "MATARAM",
    #         "district_name": "MATARAM",
    #         "subdistrict_name": "MATARAM",
    #         "zip_code": "12455",
    #         "street_address": "Jl. Test 2",
    #     })

    #     self.assertEqual(res_post.status_code, 201)

    #     res = self.client.get(reverse("shipping_address"))

    #     self.assertEqual(len(res.data), 2)

    #     data = res.data[1]
    #     self.assertEqual(data["province"]["ro_id"], 1)
    #     self.assertEqual(data["province"]["name"], "NUSA TENGGARA BARAT (NTB)")

    #     self.assertEqual(data["city"]["ro_id"], 1)
    #     self.assertEqual(data["city"]["name"], "MATARAM")

    #     self.assertEqual(data["district"]["ro_id"], 1)
    #     self.assertEqual(data["district"]["name"], "MATARAM")

    #     self.assertEqual(data["subdistrict"]["ro_id"], 1)
    #     self.assertEqual(data["subdistrict"]["name"], "MATARAM")
    #     self.assertEqual(data["subdistrict"]["zip_code"], "12455")

    #     self.assertEqual(data["street_address"], "Jl. Test 2")
    #     self.assertEqual(data["created_at"], "2025-12-08T11:45:00+07:00")
    #     self.assertEqual(data["updated_at"], "2025-12-08T11:45:00+07:00")

    #     self.assertEqual(len(data["users"]), 2)
    #     self.assertEqual(data["users"][0]["id"], 2)
    #     self.assertEqual(data["users"][0]["username"], "test2")
    #     self.assertEqual(data["users"][0]["email"], "test2@gmail.com")

    #     self.assertEqual(data["users"][1]["id"], 1)
    #     self.assertEqual(data["users"][1]["username"], "test")
    #     self.assertEqual(data["users"][1]["email"], "test@gmail.com")

    #     # mengecek data tidak dibuat, tapi ngambil data yang sudah ada
    #     # data ada 2, 2 dari setup
    #     shipping_address = ShippingAddress.objects.all()
    #     self.assertEqual(len(shipping_address), 2)

    @freeze_time("2025-12-16T19:07:00+07:00")
    @patch("accounts.signals.logger")
    def test_put(self, mock_logger):
        self.handle_login()
        res_put = self.client.put(
            reverse("shipping_address", args=[1]),
            data={
                "province_name": "NUSA TENGGARA BARAT (NTB)",
                "city_name": "MATARAM",
                "district_name": "MATARAM",
                "subdistrict_name": "MATARAM",
                "zip_code": "12455",
                "street_address": "Jl. Put",
                "is_default": True,
            },
        )

        self.assertEqual(res_put.status_code, 200)

        data = res_put.data

        self.assertEqual(data["street_address"], "Jl. Put")
        self.assertEqual(data["created_at"], "2025-12-08T11:45:00+07:00")
        self.assertEqual(data["updated_at"], "2025-12-16T19:07:00+07:00")
        self.assertTrue(data["is_default"])

        self.assertEqual(data["user"]["id"], 1)
        self.assertEqual(data["user"]["username"], "test")
        self.assertEqual(data["user"]["email"], "test@gmail.com")

    @freeze_time("2025-12-16T19:07:00+07:00")
    @patch("accounts.signals.logger")
    def test_put_is_default(self, mock_logger):
        """
        Data milik user2
        data ke 1 > id 2, data ke 2 > id 3
        Merubah data ke 2 menjadi is_default true, yang sebelumnya false dan is_default true ada di data ke 2 yang membuat
        data ke 1 field is_default menjadi false dan data ke 2 menjadi field is_default true
        """
        self.handle_login(self.user2)
        res_put = self.client.put(
            reverse("shipping_address", args=[3]),
            data={
                "province_name": "NUSA TENGGARA BARAT (NTB)",
                "city_name": "MATARAM",
                "district_name": "MATARAM",
                "subdistrict_name": "MATARAM",
                "zip_code": "12455",
                "street_address": "Jl. Put",
                "is_default": True,
            },
        )

        self.assertEqual(res_put.status_code, 200)

        data = res_put.data
        self.assertEqual(data["street_address"], "Jl. Put")
        self.assertEqual(data["created_at"], "2025-12-08T11:45:00+07:00")
        self.assertEqual(data["updated_at"], "2025-12-16T19:07:00+07:00")
        self.assertTrue(data["is_default"])

        self.assertEqual(data["user"]["id"], 2)
        self.assertEqual(data["user"]["username"], "test2")
        self.assertEqual(data["user"]["email"], "test2@gmail.com")

        # self.shipping_address2 > user2 data 1
        # mengecek data ke 1 is_default true sebelumnya
        # data ke 1 field is_default menjadi False
        self.assertTrue(self.shipping_address2.is_default)
        self.shipping_address2.refresh_from_db()
        self.assertFalse(self.shipping_address2.is_default)

        # self.shipping_address3 > user2 data 2
        # mengecek data ke 2 is_default false sebelumnya
        # data ke 2 field is_default menjadi true
        self.assertFalse(self.shipping_address3.is_default)
        self.shipping_address3.refresh_from_db()
        self.assertTrue(self.shipping_address3.is_default)

        # mengecek data yang is_default true hanya ada 1
        self.assertEqual(
            len(ShippingAddress.objects.filter(is_default=True, user=self.user2)), 1
        )

    @patch("accounts.signals.logger")
    def test_delete(self, mock_logger):
        self.handle_login()
        res_delete = self.client.delete(reverse("shipping_address", args=[1]))

        self.assertEqual(res_delete.status_code, 204)

        self.assertEqual(res_delete.data["detail"], "Item deleted")

        # cek data terhapus
        shipping_address = ShippingAddress.objects.filter(id=1).first()
        self.assertIsNone(shipping_address)
