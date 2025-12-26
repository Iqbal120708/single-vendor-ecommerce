import uuid
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from freezegun import freeze_time
from rest_framework.test import APIClient

from order.models import Order
from product.models import Product
from store.models import Store

from django.test import TransactionTestCase
import hashlib
from django.conf import settings
from django.utils import timezone
User = get_user_model()

localtime = timezone.localtime(timezone.now())
@freeze_time(localtime.isoformat())
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

        self.data_webhook = {
          "transaction_time": "2023-11-15 18:45:13",
          "transaction_status": "settlement",
          "transaction_id": "513f1f01-c9da-474c-9fc9-d5c64364b709",
          "status_message": "midtrans payment notification",
          "status_code": "200",
          #"signature_key": "0177491285b9c48d0c6b974253c32cd2d4bb3436e5e524c7487b87d2851eec558945799da39d48f73d387c72686ef6fb7f9ae4c48d8ca3cf2e88c14f9eb96fb3",
          "settlement_time": "2023-11-15 22:45:13",
          "payment_type": "gopay",
          #"order_id": "payment_notif_test_G823851098_34cafed4-f5e9-45a1-9324-7e1636a57eec",
          "merchant_id": "G823851098",
          "gross_amount": "105000.00",
          "fraud_status": "accept",
          "currency": "IDR"
        }

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
    @patch("order.utils_midtrans.logger_error")
    def test(
        self,
        order_logger_error_util_webhook,
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
        
        # ambil Product
        product = Product.objects.get(id=1)
        
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
        
        # ambil order
        orders = Order.objects.all()
        self.assertEqual(len(orders), 1)
        order = orders.first()

        raw = (
            str(order.order_id)
            + "200" # status_code
            + "105000.00" # gross_amount
            + settings.MIDTRANS_SERVER_KEY
        )
        
        signature = hashlib.sha512(raw.encode()).hexdigest()
        self.data_webhook["signature_key"] = signature
        self.data_webhook["order_id"] = str(order.order_id)
        
        # kirim webhook midtrans
        res = self.client.post(reverse("midtrans_webhook"), data=self.data_webhook, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["detail"], "Order berhasil diproses")
        
        
        # cek status order sebelum
        self.assertEqual(order.payment_status, "unpaid")
        self.assertIsNone(order.order_id_ro)
        self.assertIsNone(order.order_no_ro)
        
        # cek status order sesudah
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "paid")
        self.assertIsNotNone(order.order_id_ro)
        self.assertIsNotNone(order.order_no_ro)
        
        # stock product sebelum
        self.assertEqual(product.stock, 50)
        
        # stock product sesudah
        product.refresh_from_db()
        self.assertEqual(product.stock, 47) # dikurangi cart qty (3)
        
        # logger
        order_log_view.info.assert_called()
        logs = order_log_view.info.call_args_list
        
        self.assertEqual(len(logs), 3)
        self.assertEqual(logs[0].args[0], f"User 1 sudah melakukan transaksi untuk order_id: {order.order_id}")
        self.assertEqual(
            logs[1].args[0],
            f"Berhasil membuat order RajaOngkir untuk user 1 dengan order_id {order.order_id}",
        )
        self.assertEqual(
            logs[2].args[0],
            f"Transaksi Midtrans untuk order id {order.order_id} berhasil di proses",
        )