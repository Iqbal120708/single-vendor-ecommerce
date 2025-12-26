import uuid
from decimal import Decimal
from unittest.mock import patch

# from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from freezegun import freeze_time
from rest_framework.test import APIClient

from order.models import Order
from store.models import Store

# from store.models import Store
# from shipping_address.models import Province, City, District, SubDistrict, ShippingAddress
from django.test import TransactionTestCase

User = get_user_model()


@freeze_time("2025-12-08T11:45:00+07:00")
class TransactionTest(TransactionTestCase):
    reset_sequences = True
    def setUp(self):
        self.client = APIClient()
        call_command("seed_product")
        call_command("seed_couriers")
        call_command("data_test_user")
        call_command("data_test_store")

        self.user = User.objects.get(email="test@gmail.com")
        self.store = Store.objects.get(email="store@gmail.com")

    def handle_login(self):
        login = self.client.post(
            reverse("rest_login"),
            {"email": self.user.email, "password": "test2938484jr"},
            format="json",
        )

        self.assertEqual(login.status_code, 200)

        token = login.data["access"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def handle_refresh(self):
        refresh = self.client.post(
            reverse("token_refresh"),
            data={},
            format="json",
        )

        self.assertEqual(refresh.status_code, 200)

        token = refresh.data["access"]

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
        res_checkout = self.client.post(
            reverse("checkout"), data={"cart_ids": [res_add.data["id"]]}, format="json"
        )
        self.assertEqual(res_checkout.status_code, 200)

        # transaction
        data = {
            "checkout_id": res_checkout.data["checkout_id"],
            "code": res_checkout.data["shipping_options"][0]["code"],
            "service": res_checkout.data["shipping_options"][0]["service"],
            "cost": res_checkout.data["shipping_options"][0]["cost"],
        }
        res = self.client.post(reverse("transaction"), data=data, format="json")

        self.assertEqual(res.status_code, 200)
        self.assertIn("snap_token", res.data)

        orders = Order.objects.all()
        self.assertEqual(len(orders), 1)

        order = orders.first()
        # 1. Test Identitas & Relasi
        self.assertIsInstance(order.order_id, uuid.UUID)
        self.assertEqual(order.user, self.user)
        self.assertEqual(order.store, self.store)

        # 2. Test Enums (Choices)
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(order.payment_method, Order.PaymentMethod.BANK_TRANSFER)
        self.assertEqual(order.payment_status, Order.PaymentStatus.UNPAID)

        # 3. Test Field Angka (Integer & Decimal)
        self.assertEqual(
            order.shipping_cost, res_checkout.data["shipping_options"][0]["cost"]
        )
        self.assertEqual(order.shipping_cashback, 0)
        self.assertEqual(order.service_fee, 0)
        self.assertEqual(order.additional_cost, 0)
        self.assertEqual(order.cod_value, 0)
        self.assertNotEqual(float(order.insurance_value), 0)
        self.assertNotEqual(order.grand_total, 0)

        # 4. Test Field Alamat & Kurir
        self.assertEqual(
            order.courier_code, res_checkout.data["shipping_options"][0]["code"]
        )
        self.assertEqual(
            order.shipping_type, res_checkout.data["shipping_options"][0]["service"]
        )

        # pastikan data tidak kosong atau 0
        self.assertTrue(order.origin_ro)
        self.assertTrue(order.origin_address)
        self.assertTrue(order.destination_ro)
        self.assertTrue(order.destination_address)

        # 5. Test Boolean
        self.assertFalse(order.is_archived)

        # 6. Test DateTime
        self.assertIsNone(order.delivered_at)
        self.assertIsNone(order.canceled_at)
        self.assertIsNotNone(order.created_at)
        self.assertIsNotNone(order.updated_at)

        # 7. Test OrderItem
        self.assertEqual(len(order.items.all()), 1)
        orderitem = order.items.first()
        self.assertEqual(orderitem.product.id, 1)
        self.assertNotEqual(int(orderitem.product_price), 0)
        self.assertTrue(isinstance(orderitem.product_price, Decimal))
        self.assertEqual(orderitem.qty, 3)
        self.assertNotEqual(orderitem.subtotal, 0)
        # pastikan lebih besar dari harga product karena nilai dikali quantity (qty)
        self.assertGreater(orderitem.subtotal, orderitem.product_price)
        

    @patch("accounts.signals.logger")
    @patch("order.views.logger")
    @patch("order.views.logger_error")
    @patch("order.utils.logger")
    @patch("order.utils.logger_error")
    def test_clean_model(
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
        res_checkout = self.client.post(
            reverse("checkout"), data={"cart_ids": [res_add.data["id"]]}, format="json"
        )
        self.assertEqual(res_checkout.status_code, 200)

        # transaction
        data = {
            "checkout_id": res_checkout.data["checkout_id"],
            "code": res_checkout.data["shipping_options"][0]["code"],
            "service": res_checkout.data["shipping_options"][0]["service"],
            "cost": res_checkout.data["shipping_options"][0]["cost"],
        }
        res = self.client.post(reverse("transaction"), data=data, format="json")

        self.assertEqual(res.status_code, 200)
        self.assertIn("snap_token", res.data)

        orders = Order.objects.all()
        self.assertEqual(len(orders), 1)

        order = orders.first()

        self.assertNotEqual(order.payment_method, "COD")
        self.assertEqual(order.payment_status, "unpaid")

        with self.assertRaises(ValidationError) as ctx:
            order.status = "shipped"
            order.save()

            self.assertEqual(
                ctx,
                "Status order harus 'pending' jika payment masih 'unpaid' di pembayaran selain COD.",
            )

    @patch("accounts.signals.logger")
    @patch("order.views.logger")
    @patch("order.views.logger_error")
    @patch("order.utils.logger")
    @patch("order.utils.logger_error")
    def test_cache_data_expired(
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
        res_checkout = self.client.post(
            reverse("checkout"), data={"cart_ids": [res_add.data["id"]]}, format="json"
        )
        self.assertEqual(res_checkout.status_code, 200)

        # transaction
        data = {
            "checkout_id": res_checkout.data["checkout_id"],
            "code": res_checkout.data["shipping_options"][0]["code"],
            "service": res_checkout.data["shipping_options"][0]["service"],
            "cost": res_checkout.data["shipping_options"][0]["cost"],
        }
        # tambah 10 menit dari 45 > 55
        with freeze_time("2025-12-08T11:55:00+07:00"):
            self.handle_refresh()

            res = self.client.post(reverse("transaction"), data=data, format="json")
            self.assertEqual(res.status_code, 408)
            self.assertEqual(
                res.data["error"],
                "Sesi telah berakhir atau tidak ditemukan. Silakan ulangi proses (Maks. 10 menit).",
            )
