from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from freezegun import freeze_time
from rest_framework.test import APIClient

from shipping_address.models import (City, District, Province, ShippingAddress,
                                     SubDistrict)
from store.models import Store
from order.models import CheckoutSession
import uuid
from datetime import datetime
from django.utils import timezone

User = get_user_model()


def res_test_success(self, res):
    data = res.data

    self.assertEqual(res.status_code, 200)

    # 2. Validasi checkout_id (Format UUID)
    self.assertIn("checkout_id", data)
    self.assertIsInstance(data["checkout_id"], str)
    self.assertEqual(len(data["checkout_id"]), 36)  # Panjang standar UUID

    # 3. Validasi shipping_options
    self.assertIn("shipping_options", data)
    self.assertIsInstance(data["shipping_options"], list)
    self.assertGreater(len(data["shipping_options"]), 0)

    # 4. Ambil satu item sampel untuk validasi struktur object di dalamnya
    first_option = data["shipping_options"][0]
    expected_keys = ["name", "code", "service", "description", "cost", "etd"]
    for key in expected_keys:
        self.assertIn(key, first_option)

    # 5. Validasi tipe data field penting
    self.assertIsInstance(first_option["cost"], int)
    self.assertIsInstance(first_option["code"], str)

    # 6. Validasi data spesifik (Opsional)
    # Misalnya, mengecek apakah kurir 'tiki' ada dalam daftar
    codes = [option["code"] for option in data["shipping_options"]]

    self.assertIn("tiki", codes)
    self.assertIn("jne", codes)
    self.assertIn("ninja", codes)
    self.assertIn("pos", codes)
    self.assertIn("jnt", codes)
    self.assertNotIn("sicepat", codes)
    self.assertNotIn("ide", codes)

    # 7. Memastikan harga/cost masuk akal (tidak negatif)
    self.assertTrue(all(option["cost"] >= 0 for option in data["shipping_options"]))
    
    # 8. Test CheckoutSession
    checkout_sessions = CheckoutSession.objects.all()
    self.assertEqual(len(checkout_sessions),1)
    
    checkout_session = checkout_sessions.first()
    self.assertTrue(isinstance(checkout_session.id, uuid.UUID))
    self.assertEqual(checkout_session.cart_ids, [1])
    self.assertEqual(checkout_session.user.email, "test@gmail.com")
    self.assertEqual(len(checkout_session.user.shippingaddress_set.all()), 1)
    self.assertEqual(checkout_session.destination, checkout_session.user.shippingaddress_set.first())
    self.assertEqual(checkout_session.store.email, "store@gmail.com")
    
    # value di tambah 10 menit dari menit 45 jadi 55
    # value di convert dari lokal ke utc (jam 11 > jam 4)
    self.assertEqual(checkout_session.expires_at.strftime("%Y-%m-%d %H:%M:%S"), "2025-12-08 04:55:00")

@freeze_time("2025-12-08T11:45:00+07:00")
class CheckoutTest(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.client = APIClient()

        call_command("seed_product")
        call_command("seed_couriers")

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

        # 1. Membuat Superuser
        self.superuser = User.objects.create_superuser(
            username="admin_test",
            email="admin@example.com",
            password="adminpassword123",
            phone_number="081234567890",
        )

        EmailAddress.objects.create(
            user=self.superuser, email=self.superuser.email, verified=True, primary=True
        )

        # 2. Membuat Data Wilayah Baru (ro_id=2)
        self.province_2 = Province.objects.create(ro_id=2, name="JAWA BARAT")

        self.city_2 = City.objects.create(
            ro_id=2, name="BANDUNG", province=self.province_2
        )

        self.district_2 = District.objects.create(
            ro_id=2, name="COBLONG", city=self.city_2
        )

        self.subdistrict_2 = SubDistrict.objects.create(
            ro_id=2, name="DAGO", zip_code="40135", district=self.district_2
        )

        # 3. Membuat Shipping Address Kedua (untuk superuser)
        self.shipping_address_2 = ShippingAddress.objects.create(
            province=self.province_2,
            city=self.city_2,
            district=self.district_2,
            subdistrict=self.subdistrict_2,
            street_address="Jl. Dago No. 123",
            is_default=True,
            user=self.superuser,
        )

        self.store = Store.objects.create(
            brand_name="Store Test",
            name="Store",
            email="store@gmail.com",
            phone_number="080987654321",
            shipping_address=self.shipping_address_2,
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
    @patch("order.views.logger")
    @patch("order.views.logger_error")
    @patch("order.utils.logger")
    @patch("order.utils.logger_error")
    def test(
        self,
        order_logger_error_util,
        order_log_util,
        order_logger_error_view,
        order_log_view,
        mock_logger,
    ):
        self.handle_login()
        # add cart
        res_add = self.client.post(reverse("add_to_cart", args=[1]), data={})
        self.assertEqual(res_add.status_code, 201)

        # update cart
        res_patch = self.client.patch(
            reverse("cart", args=[res_add.data["id"]]), data={"qty": 3}
        )
        self.assertEqual(res_patch.status_code, 200)

        # checkout
        res = self.client.post(
            reverse("checkout"), data={"cart_ids": [res_add.data["id"]]}, format="json"
        )

        res_test_success(self, res)

        order_log_view.info.assert_called()
        logs = order_log_view.info.call_args_list

        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[0].args[0], "User 1 memulai checkout untuk cart_ids: [1]")
        self.assertEqual(
            logs[1].args[0],
            f"Checkout Session {res.data['checkout_id']} dibuat untuk User 1. Data disimpan di model.",
        )

    @patch("accounts.signals.logger")
    @patch("order.views.logger")
    @patch("order.views.logger_error")
    @patch("order.utils.logger")
    @patch("order.utils.logger_error")
    def test_with_ship_addr_id(
        self,
        order_logger_error_util,
        order_log_util,
        order_logger_error_view,
        order_log_view,
        mock_logger,
    ):
        """
        this test used key shipping_address_id in body request
        response remains the same
        """
        self.handle_login()
        # add cart
        res_add = self.client.post(reverse("add_to_cart", args=[1]), data={})
        self.assertEqual(res_add.status_code, 201)

        # update cart
        res_patch = self.client.patch(
            reverse("cart", args=[res_add.data["id"]]), data={"qty": 3}
        )
        self.assertEqual(res_patch.status_code, 200)

        # checkout
        res = self.client.post(
            reverse("checkout"),
            data={
                "cart_ids": [res_add.data["id"]],
                "shipping_address_id": self.shipping_address.id,
            },
            format="json",
        )

        res_test_success(self, res)

        order_log_view.info.assert_called()
        logs = order_log_view.info.call_args_list

        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[0].args[0], "User 1 memulai checkout untuk cart_ids: [1]")
        self.assertEqual(
            logs[1].args[0],
            f"Checkout Session {res.data['checkout_id']} dibuat untuk User 1. Data disimpan di model.",
        )

    @patch("accounts.signals.logger")
    @patch("order.views.logger")
    @patch("order.views.logger_error")
    @patch("order.utils.logger")
    @patch("order.utils.logger_error")
    def test_error_data_cart_ids(
        self,
        order_logger_error_util,
        order_log_util,
        order_logger_error_view,
        order_log_view,
        mock_logger,
    ):
        self.handle_login()
        # add cart
        res_add = self.client.post(reverse("add_to_cart", args=[1]), data={})
        self.assertEqual(res_add.status_code, 201)

        # update cart
        res_patch = self.client.patch(
            reverse("cart", args=[res_add.data["id"]]), data={"qty": 3}
        )

        self.assertEqual(res_patch.status_code, 200)

        # checkout cart_ids nothing
        res = self.client.post(reverse("checkout"), data={}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(
            res.data["error"], "cart_ids harus berupa list dan tidak boleh kosong."
        )

        # checkout cart_ids != list
        res = self.client.post(reverse("checkout"), data={"cart_ids": 1}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(
            res.data["error"], "cart_ids harus berupa list dan tidak boleh kosong."
        )

        # checkout list cart_ids != integer
        res = self.client.post(
            reverse("checkout"), data={"cart_ids": ["a"]}, format="json"
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(
            res.data["error"],
            "Semua item di dalam cart_ids harus berupa angka (integer).",
        )

        order_log_view.info.assert_called()
        logs = order_log_view.info.call_args_list

        # ada 3 request permintaan dan gagal jadi hanya bikin 3 log info start checkout
        self.assertEqual(len(logs), 3)
        self.assertEqual(
            logs[0].args[0], "User 1 memulai checkout untuk cart_ids: None"
        )
        self.assertEqual(logs[1].args[0], "User 1 memulai checkout untuk cart_ids: 1")
        self.assertEqual(
            logs[2].args[0], "User 1 memulai checkout untuk cart_ids: ['a']"
        )

    @patch("accounts.signals.logger")
    @patch("order.views.logger")
    @patch("order.views.logger_error")
    @patch("order.utils.logger")
    @patch("order.utils.logger_error")
    def test_error_store_origin(
        self,
        order_logger_error_util,
        order_log_util,
        order_logger_error_view,
        order_log_view,
        mock_logger,
    ):
        """
        This test when store not found which makes origin address cannot be accessed
        """
        self.handle_login()
        # add cart
        res_add = self.client.post(reverse("add_to_cart", args=[1]), data={})
        self.assertEqual(res_add.status_code, 201)

        # update cart
        res_patch = self.client.patch(
            reverse("cart", args=[res_add.data["id"]]), data={"qty": 3}
        )
        self.assertEqual(res_patch.status_code, 200)

        # buat store tidak aktif agar gak bisa di pakai
        self.store.is_active = False
        self.store.save()

        # checkout
        res = self.client.post(
            reverse("checkout"), data={"cart_ids": [res_add.data["id"]]}, format="json"
        )

        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["error"], "Toko tidak ditemukan.")

        order_log_view.info.assert_called()
        logs = order_log_view.info.call_args_list

        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].args[0], "User 1 memulai checkout untuk cart_ids: [1]")

        order_logger_error_view.error.assert_called()
        args, kwargs = order_logger_error_view.error.call_args

        self.assertEqual(args[0], "Store aktif tidak ditemukan. User ID: 1")

    @patch("accounts.signals.logger")
    @patch("order.views.logger")
    @patch("order.views.logger_error")
    @patch("order.utils.logger")
    @patch("order.utils.logger_error")
    def test_error_destination(
        self,
        order_logger_error_util,
        order_log_util,
        order_logger_error_view,
        order_log_view,
        mock_logger,
    ):
        """
        This test when shipping_address not found which makes destination address cannot be accessed
        """
        self.handle_login()
        # add cart
        res_add = self.client.post(reverse("add_to_cart", args=[1]), data={})
        self.assertEqual(res_add.status_code, 201)

        # update cart
        res_patch = self.client.patch(
            reverse("cart", args=[res_add.data["id"]]), data={"qty": 3}
        )
        self.assertEqual(res_patch.status_code, 200)

        # delete shipping_address user
        self.shipping_address.delete()

        # checkout
        res = self.client.post(
            reverse("checkout"), data={"cart_ids": [res_add.data["id"]]}, format="json"
        )

        self.assertEqual(res.status_code, 400)
        self.assertEqual(
            res.data["error"],
            "Alamat pengiriman belum dipilih. Silakan pilih salah satu alamat Anda atau atur salah satu sebagai 'Alamat Utama' (Default).",
        )

        order_log_view.info.assert_called()
        logs = order_log_view.info.call_args_list

        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].args[0], "User 1 memulai checkout untuk cart_ids: [1]")

        order_log_util.warning.assert_called()
        args, kwargs = order_log_util.warning.call_args

        self.assertEqual(
            args[0],
            "Destination tidak ditemukan. User ID: 1, Address ID Provided: None",
        )

    @patch("accounts.signals.logger")
    @patch("order.views.logger")
    @patch("order.views.logger_error")
    @patch("order.utils.logger")
    @patch("order.utils.logger_error")
    @override_settings(API_KEY_RAJA_ONGKIR="invalid key")
    def test_error_api_key(
        self,
        order_logger_error_util,
        order_log_util,
        order_logger_error_view,
        order_log_view,
        mock_logger,
    ):

        self.handle_login()
        # add cart
        res_add = self.client.post(reverse("add_to_cart", args=[1]), data={})
        self.assertEqual(res_add.status_code, 201)

        # update cart
        res_patch = self.client.patch(
            reverse("cart", args=[res_add.data["id"]]), data={"qty": 3}
        )
        self.assertEqual(res_patch.status_code, 200)

        # checkout
        res = self.client.post(
            reverse("checkout"), data={"cart_ids": [res_add.data["id"]]}, format="json"
        )

        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["error"], "Invalid Api key, key not found")

        order_log_view.info.assert_called()
        logs = order_log_view.info.call_args_list

        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].args[0], "User 1 memulai checkout untuk cart_ids: [1]")

        order_logger_error_view.error.assert_called()
        args, kwargs = order_logger_error_view.error.call_args

        self.assertEqual(
            args[0],
            "Gagal mengambil ongkir RajaOngkir untuk User 1. Error: Invalid Api key, key not found",
        )
        self.assertEqual(kwargs["extra"]["event_type"], "checkout")
        self.assertIn("origin", kwargs["extra"])
        self.assertIn("destination", kwargs["extra"])
        self.assertIn("weight", kwargs["extra"])
        self.assertIn("courier", kwargs["extra"])
