# import uuid
# from decimal import Decimal
# from unittest.mock import patch

# # from allauth.account.models import EmailAddress
# from django.contrib.auth import get_user_model
# from django.core.exceptions import ValidationError
# from django.core.management import call_command

# # from store.models import Store
# # from shipping_address.models import Province, City, District, SubDistrict, ShippingAddress
# from django.test import TransactionTestCase, override_settings
# from django.urls import reverse
# from freezegun import freeze_time
# from order.models import Order
# from rest_framework.test import APIClient
# from store.models import Store

# User = get_user_model()


# @freeze_time("2025-12-08T11:45:00+07:00")
# class TransactionTest(TransactionTestCase):
#     reset_sequences = True

#     def setUp(self):
#         self.client = APIClient()
#         call_command("seed_product")
#         call_command("seed_couriers")
#         call_command("data_test_user")
#         call_command("data_test_store")

#         self.user = User.objects.get(email="test@gmail.com")
#         self.store = Store.objects.get(email="store@gmail.com")

#     def handle_login(self):
#         login = self.client.post(
#             reverse("rest_login"),
#             {"email": self.user.email, "password": "test2938484jr"},
#             format="json",
#         )

#         self.assertEqual(login.status_code, 200)

#         token = login.data["access"]

#         self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

#     def handle_refresh(self):
#         refresh = self.client.post(
#             reverse("token_refresh"),
#             data={},
#             format="json",
#         )

#         self.assertEqual(refresh.status_code, 200)

#         token = refresh.data["access"]

#         self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

#     @patch("accounts.signals.logger")
#     @patch("order.views_order_process.logger")
#     @patch("order.views_order_process.logger_error")
#     @patch("order.utils.logger")
#     @patch("order.utils.logger_error")
#     def test(
#         self,
#         order_logger_error_util,
#         order_log_util,
#         order_logger_error_view,
#         order_log_view,
#         mock_logger,
#     ):
#         self.handle_login()
#         # add cart
#         res_add = self.client.post(reverse("add_to_cart", args=[1]), data={})
#         self.assertEqual(res_add.status_code, 201)

#         # update cart
#         res_patch = self.client.patch(
#             reverse("cart", args=[res_add.data["id"]]), data={"qty": 3}
#         )
#         self.assertEqual(res_patch.status_code, 200)

#         # checkout
#         res_checkout = self.client.post(
#             reverse("checkout"), data={"cart_ids": [res_add.data["id"]]}, format="json"
#         )
#         self.assertEqual(res_checkout.status_code, 200)

#         # transaction
#         data = {
#             "checkout_id": res_checkout.data["checkout_id"],
#             "code": res_checkout.data["shipping_options"][0]["code"],
#             "service": res_checkout.data["shipping_options"][0]["service"],
#             "cost": res_checkout.data["shipping_options"][0]["cost"],
#         }
#         res = self.client.post(reverse("transaction"), data=data, format="json")

#         self.assertEqual(res.status_code, 200)
#         self.assertIn("snap_token", res.data)

#         orders = Order.objects.all()
#         self.assertEqual(len(orders), 1)

#         order = orders.first()
#         # 1. Test Identitas & Relasi
#         self.assertIsInstance(order.order_id, uuid.UUID)
#         self.assertEqual(order.user, self.user)
#         self.assertEqual(order.store, self.store)

#         # 2. Test Enums (Choices)
#         self.assertEqual(order.status, Order.Status.PENDING)
#         self.assertEqual(order.payment_method, Order.PaymentMethod.BANK_TRANSFER)
#         self.assertEqual(order.payment_status, Order.PaymentStatus.UNPAID)

#         # 3. Test Field Angka (Integer & Decimal)
#         self.assertEqual(
#             order.shipping_cost, res_checkout.data["shipping_options"][0]["cost"]
#         )
#         self.assertEqual(order.shipping_cashback, 0)
#         self.assertEqual(order.service_fee, 0)
#         self.assertEqual(order.additional_cost, 0)
#         self.assertEqual(order.cod_value, 0)
#         self.assertNotEqual(float(order.insurance_value), 0)
#         self.assertNotEqual(order.grand_total, 0)

#         # 4. Test Field Alamat & Kurir
#         self.assertEqual(
#             order.courier_code, res_checkout.data["shipping_options"][0]["code"]
#         )
#         self.assertEqual(
#             order.shipping_type, res_checkout.data["shipping_options"][0]["service"]
#         )

#         # pastikan data tidak kosong atau 0
#         self.assertTrue(order.origin_ro)
#         self.assertTrue(order.origin_address)
#         self.assertTrue(order.destination_ro)
#         self.assertTrue(order.destination_address)

#         # 5. Test Boolean
#         # self.assertFalse(order.is_archived)

#         # 6. Test DateTime
#         self.assertIsNone(order.delivered_at)
#         self.assertIsNone(order.canceled_at)
#         self.assertIsNotNone(order.created_at)
#         self.assertIsNotNone(order.updated_at)

#         # 7. Test OrderItem
#         self.assertEqual(len(order.items.all()), 1)
#         orderitem = order.items.first()
#         self.assertEqual(orderitem.product.id, 1)
#         self.assertNotEqual(int(orderitem.product_price), 0)
#         self.assertTrue(isinstance(orderitem.product_price, Decimal))
#         self.assertEqual(orderitem.qty, 3)
#         self.assertNotEqual(orderitem.subtotal, 0)
#         # pastikan lebih besar dari harga product karena nilai dikali quantity (qty)
#         self.assertGreater(orderitem.subtotal, orderitem.product_price)

#     @patch("accounts.signals.logger")
#     @patch("order.views_order_process.logger")
#     @patch("order.views_order_process.logger_error")
#     @patch("order.utils.logger")
#     @patch("order.utils.logger_error")
#     def test_clean_model(
#         self,
#         order_logger_error_util,
#         order_log_util,
#         order_logger_error_view,
#         order_log_view,
#         mock_logger,
#     ):
#         self.handle_login()
#         # add cart
#         res_add = self.client.post(reverse("add_to_cart", args=[1]), data={})
#         self.assertEqual(res_add.status_code, 201)

#         # update cart
#         res_patch = self.client.patch(
#             reverse("cart", args=[res_add.data["id"]]), data={"qty": 3}
#         )
#         self.assertEqual(res_patch.status_code, 200)

#         # checkout
#         res_checkout = self.client.post(
#             reverse("checkout"), data={"cart_ids": [res_add.data["id"]]}, format="json"
#         )
#         self.assertEqual(res_checkout.status_code, 200)

#         # transaction
#         data = {
#             "checkout_id": res_checkout.data["checkout_id"],
#             "code": res_checkout.data["shipping_options"][0]["code"],
#             "service": res_checkout.data["shipping_options"][0]["service"],
#             "cost": res_checkout.data["shipping_options"][0]["cost"],
#         }
#         res = self.client.post(reverse("transaction"), data=data, format="json")

#         self.assertEqual(res.status_code, 200)
#         self.assertIn("snap_token", res.data)

#         orders = Order.objects.all()
#         self.assertEqual(len(orders), 1)

#         order = orders.first()

#         self.assertNotEqual(order.payment_method, "COD")
#         self.assertEqual(order.payment_status, "unpaid")

#         with self.assertRaises(ValidationError) as ctx:
#             order.status = "shipped"
#             order.save()

#             self.assertEqual(
#                 ctx,
#                 "Status order harus 'pending' jika payment masih 'unpaid' di pembayaran selain COD.",
#             )

#     @patch("accounts.signals.logger")
#     @patch("order.views_order_process.logger")
#     @patch("order.views_order_process.logger_error")
#     @patch("order.utils.logger")
#     @patch("order.utils.logger_error")
#     def test_cache_data_expired(
#         self,
#         order_logger_error_util,
#         order_log_util,
#         order_logger_error_view,
#         order_log_view,
#         mock_logger,
#     ):
#         self.handle_login()
#         # add cart
#         res_add = self.client.post(reverse("add_to_cart", args=[1]), data={})
#         self.assertEqual(res_add.status_code, 201)

#         # update cart
#         res_patch = self.client.patch(
#             reverse("cart", args=[res_add.data["id"]]), data={"qty": 3}
#         )
#         self.assertEqual(res_patch.status_code, 200)

#         # checkout
#         res_checkout = self.client.post(
#             reverse("checkout"), data={"cart_ids": [res_add.data["id"]]}, format="json"
#         )
#         self.assertEqual(res_checkout.status_code, 200)

#         # transaction
#         data = {
#             "checkout_id": res_checkout.data["checkout_id"],
#             "code": res_checkout.data["shipping_options"][0]["code"],
#             "service": res_checkout.data["shipping_options"][0]["service"],
#             "cost": res_checkout.data["shipping_options"][0]["cost"],
#         }
#         # tambah 10 menit dari 45 > 55
#         with freeze_time("2025-12-08T11:55:00+07:00"):
#             self.handle_refresh()

#             res = self.client.post(reverse("transaction"), data=data, format="json")
#             self.assertEqual(res.status_code, 408)
#             self.assertEqual(
#                 res.data["error"],
#                 "Sesi telah berakhir atau tidak ditemukan. Silakan ulangi proses (Maks. 10 menit).",
#             )






















from unittest.mock import patch, MagicMock

from django.test import TestCase, TransactionTestCase
from datetime import timedelta
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.exceptions import NotFound

from order.utils import CheckoutExpired, GrossAmountMismatch
from order.views_order_process import TransactionView

from cart.models import Cart
from django.core.management import call_command
from django.test import TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from order.models import CheckoutSession, Order, OrderItem, OrderShipping
from product.models import Product
from rest_framework.test import APIClient

from .helper_setup import (
    set_address,
    set_location_fields,
    set_store,
    set_store_shipping_option,
    set_user,
)

# =====================================================================
# TransactionView (APIView)
# =====================================================================
class TransactionViewTests(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = MagicMock()

        self.logger_patcher = patch(
            "order.views_order_process.logger"
        )
        self.mock_logger = self.logger_patcher.start()
        self.addCleanup(self.logger_patcher.stop)

    def _build_mock_checkout(self, has_shipping=False):
        """
        Helper: bikin mock checkout + order dengan struktur relasi lengkap.
        has_shipping=False -> simulasikan order.shipping belum ada (OneToOne
        reverse belum terbentuk) di view.
        """
        checkout = MagicMock()
        checkout.id = 1
        checkout.user.username = "budi"
        checkout.user.email = "budi@example.com"
        checkout.user.phone_number = "081234567890"
        checkout.store.insurance_paid_by_customer = False

        order = checkout.order
        order.order_id = "ORDER-1"
        order.grand_total = 100000

        item1 = MagicMock()
        item1.product.id = 5
        item1.product.name = "Kaos Polos"
        item1.product_price = 100000
        item1.qty = 1
        order.items.all.return_value.select_related.return_value = [item1]

        if has_shipping:
            order.shipping.shipping_cost = 0
            order.shipping.shipping_name = "JNE"
            order.shipping.service_name = "REG"
            order.shipping.insurance_value = 0
            order.shipping.additional_cost = 0
            order.shipping.service_fee = 0
        else:
            # Simulasikan Django OneToOne reverse accessor yang belum ada:
            # hasattr(order, 'shipping') harus False.
            order.shipping = None

        return checkout, order

    def _valid_payload(self):
        return {
            "checkout_id": 1,
            "shipping_name": "JNE",
            "service_name": "REG",
            "shipping_weight": 0.5,
            "etd": "2-3 day",
            "shipping_cost": 10000,
            "shipping_cashback": 0,
            "shipping_cost_net": 10000,
            "service_fee": 0,
            "is_cod": False,
            "net_income": 90000,
        }

    # -----------------------------------------------------------------
    # Happy path
    # -----------------------------------------------------------------
    @patch("order.views_order_process.snap")
    @patch("order.views_order_process.OrderShippingService")
    @patch("order.views_order_process.get_valid_checkout")
    def test_return_200_with_snap_token_on_success(
        self, mock_get_checkout, mock_service_cls, mock_snap
    ):
        """
        Test: checkout valid, belum ada shipping record, OrderShippingService
        sukses, gross_amount cocok, Midtrans sukses.
        Assert: response 200 dan body berisi snap_token dari Midtrans.
        """
        checkout, order = self._build_mock_checkout(has_shipping=False)
        mock_get_checkout.return_value = checkout

        def fake_execute():
            # Simulasikan side-effect: shipping record sekarang "ada"
            order.shipping = MagicMock(
                shipping_cost=10000,
                shipping_name="JNE",
                service_name="REG",
                insurance_value=0,
                additional_cost=0,
                service_fee=0,
            )
            order.grand_total = 110000  # produk 100000 + ongkir 10000
            return order.shipping

        mock_service_cls.return_value.execute.side_effect = fake_execute
        mock_snap.create_transaction.return_value = {"token": "snap-token-123"}

        request = self.factory.post("/transaction/", self._valid_payload())
        force_authenticate(request, user=self.user)
        response = TransactionView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["snap_token"], "snap-token-123")

    @patch("order.views_order_process.snap")
    @patch("order.views_order_process.OrderShippingService")
    @patch("order.views_order_process.get_valid_checkout")
    def test_order_shipping_service_always_called_even_when_shipping_exists(
        self, mock_get_checkout, mock_service_cls, mock_snap
    ):
        """
        Test: order.shipping SUDAH ada (retry kedua/ketiga kalinya).
        Assert: OrderShippingService TETAP dipanggil (bukan di-skip) --
        ini sengaja, karena skip berdasarkan hasattr() menyebabkan bug:
        kalau data (mis. harga produk) berubah di antara attempt, shipping
        record lama jadi stale dan validate_gross_amount akan mismatch
        SELAMANYA sampai checkout expired (10 menit), user tidak pernah
        bisa bayar. Solusinya: selalu re-run OrderShippingService (murni
        kalkulasi lokal, tidak ada call API, jadi aman di-re-run) supaya
        order.grand_total selalu sinkron dengan data terbaru.
        """
        checkout, order = self._build_mock_checkout(has_shipping=True)

        def fake_execute():
            # Simulasikan hasil re-run: grand_total ter-refresh ke nilai baru
            order.shipping.shipping_cost = 10000
            order.shipping.shipping_name = "JNE"
            order.shipping.service_name = "REG"
            order.shipping.insurance_value = 0
            order.shipping.additional_cost = 0
            order.shipping.service_fee = 0
            order.grand_total = 110000
            return order.shipping

        mock_get_checkout.return_value = checkout
        mock_service_cls.return_value.execute.side_effect = fake_execute
        mock_snap.create_transaction.return_value = {"token": "snap-token-retry"}

        request = self.factory.post("/transaction/", self._valid_payload())
        force_authenticate(request, user=self.user)
        response = TransactionView.as_view()(request)

        # Inti dari fix: OrderShippingService HARUS tetap dipanggil,
        # tidak boleh di-skip hanya karena order.shipping sudah ada.
        mock_service_cls.return_value.execute.assert_called_once()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["snap_token"], "snap-token-retry")

    # -----------------------------------------------------------------
    # Payload ke Midtrans: item_details & gross_amount benar
    # -----------------------------------------------------------------
    @patch("order.views_order_process.get_valid_checkout")
    def test_propagate_not_found_when_checkout_invalid(self, mock_get_checkout):
        """
        Test: get_valid_checkout raise NotFound.
        Assert: exception ter-propagate ke DRF exception handler, response 404.
        """
        mock_get_checkout.side_effect = NotFound("CheckoutSession tidak ditemukan")

        request = self.factory.post("/transaction/", self._valid_payload())
        force_authenticate(request, user=self.user)
        response = TransactionView.as_view()(request)

        self.assertEqual(response.status_code, 404)

    @patch("order.views_order_process.get_valid_checkout")
    def test_propagate_checkout_expired_when_session_expired(self, mock_get_checkout):
        """
        Test: get_valid_checkout raise CheckoutExpired.
        Assert: response status 408 sesuai status_code di CheckoutExpired,
        dan ini terjadi SEBELUM masuk atomic block (OrderShippingService
        tidak boleh sempat dipanggil).
        """
        mock_get_checkout.side_effect = CheckoutExpired()

        request = self.factory.post("/transaction/", self._valid_payload())
        force_authenticate(request, user=self.user)
        response = TransactionView.as_view()(request)

        self.assertEqual(response.status_code, 408)

    # -----------------------------------------------------------------
    # Atomic block: OrderShippingService gagal (exception generik)
    # -----------------------------------------------------------------
    @patch("order.views_order_process.logger_error")
    @patch("order.views_order_process.snap")
    @patch("order.views_order_process.OrderShippingService")
    @patch("order.views_order_process.get_valid_checkout")
    def test_return_500_and_log_when_order_shipping_service_raises(
        self, mock_get_checkout, mock_service_cls, mock_snap, mock_logger_error
    ):
        """
        Test: OrderShippingService.execute() raise exception generik (bukan
        GrossAmountMismatch) -- misal bug internal / data tidak konsisten.
        Assert: response 500 dengan pesan generik "gagal membuat order
        shipping", logger_error terpanggil, dan snap.create_transaction
        TIDAK PERNAH dipanggil (gagal duluan di atomic block).
        """
        checkout, order = self._build_mock_checkout(has_shipping=False)
        mock_get_checkout.return_value = checkout
        mock_service_cls.return_value.execute.side_effect = ValueError("data korup")

        request = self.factory.post("/transaction/", self._valid_payload())
        force_authenticate(request, user=self.user)
        response = TransactionView.as_view()(request)

        self.assertEqual(response.status_code, 500)
        mock_logger_error.error.assert_called_once()
        mock_snap.create_transaction.assert_not_called()

    # -----------------------------------------------------------------
    # Atomic block: gross_amount mismatch -> raise, bukan return
    # -----------------------------------------------------------------
    @patch("order.views_order_process.snap")
    @patch("order.views_order_process.validate_gross_amount")
    @patch("order.views_order_process.build_item_details")
    @patch("order.views_order_process.OrderShippingService")
    @patch("order.views_order_process.get_valid_checkout")
    def test_propagate_gross_amount_mismatch_with_custom_message(
        self,
        mock_get_checkout,
        mock_service_cls,
        mock_build_items,
        mock_validate_gross,
        mock_snap,
    ):
        """
        Test: validate_gross_amount raise GrossAmountMismatch.
        Assert: exception ter-propagate (bukan ditelan jadi pesan generik
        "gagal membuat order shipping"), response status dan detail message
        harus sesuai default_detail/status_code di GrossAmountMismatch itu
        sendiri, dan snap.create_transaction TIDAK PERNAH dipanggil.
        """
        checkout, order = self._build_mock_checkout(has_shipping=False)
        mock_get_checkout.return_value = checkout
        mock_service_cls.return_value.execute.return_value = MagicMock()
        mock_build_items.return_value = [{"id": "X", "price": 1, "quantity": 1, "name": "X"}]
        mock_validate_gross.side_effect = GrossAmountMismatch()

        request = self.factory.post("/transaction/", self._valid_payload())
        force_authenticate(request, user=self.user)
        response = TransactionView.as_view()(request)

        self.assertEqual(response.status_code, GrossAmountMismatch.status_code)
        self.assertEqual(response.data["detail"], GrossAmountMismatch.default_detail)
        mock_snap.create_transaction.assert_not_called()

    # -----------------------------------------------------------------
    # snap.create_transaction gagal (di luar atomic block)
    # -----------------------------------------------------------------
    @patch("order.views_order_process.logger_error")
    @patch("order.views_order_process.snap")
    @patch("order.views_order_process.OrderShippingService")
    @patch("order.views_order_process.get_valid_checkout")
    def test_return_502_when_midtrans_call_fails(
        self, mock_get_checkout, mock_service_cls, mock_snap, mock_logger_error
    ):
        """
        Test: OrderShippingService & validasi gross_amount sukses, tapi
        snap.create_transaction raise exception (Midtrans down/timeout).
        Assert: response 502 dengan pesan retry, logger_error terpanggil.
        Ini membuktikan shipping record TIDAK di-rollback hanya karena
        Midtrans gagal (bagian ini sengaja di luar atomic block).
        """
        checkout, order = self._build_mock_checkout(has_shipping=False)
        mock_get_checkout.return_value = checkout

        def fake_execute():
            order.shipping = MagicMock(
                shipping_cost=10000,
                shipping_name="JNE",
                service_name="REG",
                insurance_value=0,
                additional_cost=0,
                service_fee=0,
            )
            order.grand_total = 110000
            return order.shipping

        mock_service_cls.return_value.execute.side_effect = fake_execute
        mock_snap.create_transaction.side_effect = Exception("Midtrans timeout")

        request = self.factory.post("/transaction/", self._valid_payload())
        force_authenticate(request, user=self.user)
        response = TransactionView.as_view()(request)

        self.assertEqual(response.status_code, 502)
        mock_logger_error.error.assert_called_once()

        # Bukti tidak ada "rollback manual" di level view: objek shipping
        # yang sudah dibuat OrderShippingService tetap utuh di memory
        # setelah exception Midtrans -- tidak ada kode yang meng-clear
        # order.shipping di except block snap.
        self.assertIsNotNone(order.shipping)
        self.assertEqual(order.shipping.shipping_name, "JNE")
        
    @patch("order.views_order_process.snap")
    @patch("order.views_order_process.OrderShippingService")
    @patch("order.views_order_process.get_valid_checkout")
    def test_midtrans_payload_uses_product_id_not_product_name(
        self, mock_get_checkout, mock_service_cls, mock_snap
    ):
        """
        Test: memastikan fix bug lama tidak muncul lagi -- item_details
        "id" harus product.id (unik), bukan product.name.
        Assert: payload yang dikirim ke snap.create_transaction punya
        item id == str(product.id).
        """
        checkout, order = self._build_mock_checkout(has_shipping=False)
        mock_get_checkout.return_value = checkout

        def fake_execute():
            order.shipping = MagicMock(
                shipping_cost=10000,
                shipping_name="JNE",
                service_name="REG",
                insurance_value=0,
                additional_cost=0,
                service_fee=0,
            )
            order.grand_total = 110000
            return order.shipping

        mock_service_cls.return_value.execute.side_effect = fake_execute
        mock_snap.create_transaction.return_value = {"token": "tok"}

        request = self.factory.post("/transaction/", self._valid_payload())
        force_authenticate(request, user=self.user)
        TransactionView.as_view()(request)

        sent_payload = mock_snap.create_transaction.call_args[0][0]
        product_item = next(
            i for i in sent_payload["item_details"] if i["name"] == "Kaos Polos"
        )
        self.assertEqual(product_item["id"], "5")
        


class TransactionViewIntegrationTest(TransactionTestCase):
    """
    Integration test untuk TransactionView endpoint.

    Tujuan test ini BEDA dari unit test (TransactionViewTests di atas):
    unit test membuktikan LOGIC (exception handling, guard idempotency,
    payload construction) dengan model & service di-mock. Test ini
    membuktikan bahwa STRUKTUR model asli (relasi FK/OneToOne, nama
    field) benar-benar nyambung dan bahwa transaction.atomic() di view
    berperilaku benar terhadap database asli -- karena OrderShippingService
    (create_order_shipping, finalize_order, update_or_create) tidak pernah
    benar-benar dieksekusi lawan database asli di unit test.

    Hanya perlu skenario yang butuh DB nyata untuk dibuktikan (rollback
    behavior, retry dengan data insurance yang berubah), bukan mengulang
    semua skenario yang sudah di-cover unit test.
    """

    def setUp(self):
        self.client = APIClient()
        
        self.logger_patcher = patch("order.views_order_process.logger")
        self.mock_logger = self.logger_patcher.start()
        self.addCleanup(self.logger_patcher.stop)
        
        self.auth_logger_patcher = patch("accounts.signals.logger")
        self.mock_auth_logger = self.auth_logger_patcher.start()
        self.addCleanup(self.auth_logger_patcher.stop)
    
        call_command("seed_product")

        self.user = set_user()
        self.location_fields = set_location_fields()
        self.shipping_address = set_address(self.user, *self.location_fields)
        self.store = set_store(*self.location_fields)
        set_store_shipping_option(self.store)

        self.cart = Cart.objects.create(
            user=self.user, product=Product.objects.first(), qty=1
        )

        self.order = Order.objects.create(
            user=self.user,
            store=self.store,
        )

        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.cart.product,
            product_price=self.cart.product.price,
            qty=self.cart.qty,
        )

        self.checkout = CheckoutSession.objects.create(
            user=self.user,
            cart_ids=[1],
            destination=self.shipping_address,
            store=self.store,
            expires_at=timezone.now() + timedelta(minutes=10),
            order=self.order,
        )

    def handle_login(self):
        """Login pakai JWT asli lewat endpoint rest_login, bukan force_authenticate,
        karena ini integration test -- kita mau buktikan auth beneran jalan juga."""
        login = self.client.post(
            reverse("rest_login"),
            {"email": self.user.email, "password": "test2938484jr"},
            format="json",
        )
        self.assertEqual(login.status_code, 200)
        token = login.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _valid_payload(self):
        return {
            "checkout_id": self.checkout.id,
            "shipping_name": "JNE",
            "service_name": "CTC23",
            "shipping_weight": 0.5,
            "etd": "2-3 day",
            "shipping_cost": 10000,
            "shipping_cashback": 0,
            "shipping_cost_net": 10000,
            "service_fee": 0,
            "is_cod": False,
            "net_income": 90000,
        }
        
    @patch("order.views_order_process.snap")
    def test_happy_path_returns_snap_token_with_real_db(self, mock_snap):
        """
        Test: happy path end-to-end lawan database asli -- checkout valid,
        OrderShippingService benar-benar membuat OrderShipping (bukan mock),
        finalize_order() benar-benar menghitung grand_total, validate_gross_amount
        lolos, dan snap.create_transaction (satu-satunya bagian yang di-mock,
        karena itu call eksternal) mengembalikan token.

        Assert: response 200 + snap_token, dan OrderShipping benar-benar
        tersimpan di DB dengan grand_total order yang konsisten -- membuktikan
        relasi FK/OneToOne (checkout.store.shipping_address, checkout.destination,
        order.items) benar-benar nyambung, bukan sekadar lolos di unit test
        yang modelnya di-mock.
        """
        self.handle_login()
        mock_snap.create_transaction.return_value = {"token": "snap-token-happy"}

        response = self.client.post(
            reverse("transaction"), self._valid_payload(), format="json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["snap_token"], "snap-token-happy")

        self.order.refresh_from_db()
        self.assertTrue(
            OrderShipping.objects.filter(order=self.order).exists()
        )
        self.assertEqual(self.order.shipping.shipping_name, "JNE")
        self.assertGreater(self.order.grand_total, 0)

        # gross_amount yang dikirim ke Midtrans harus sama persis dengan
        # grand_total order -- ini bukti build_item_details + validate_gross_amount
        # konsisten dengan hasil finalize_order() yang sesungguhnya.
        sent_payload = mock_snap.create_transaction.call_args[0][0]
        self.assertEqual(
            sent_payload["transaction_details"]["gross_amount"],
            self.order.grand_total,
        )

    @patch("order.views_order_process.logger_error")
    @patch("order.views_order_process.snap")
    def test_shipping_record_persists_in_db_when_midtrans_fails(self, mock_snap, mock_logger_error):
        """
        Test: OrderShippingService.execute() benar-benar menulis
        OrderShipping ke DB (bukan mock), lalu snap.create_transaction
        raise exception.
        Assert: row OrderShipping TETAP ADA di DB setelah request selesai
        -- membuktikan bagian OrderShippingService + validasi gross_amount
        TIDAK ikut ter-rollback hanya karena Midtrans gagal, karena
        call Midtrans memang sengaja ditaruh DI LUAR
        `with db_transaction.atomic():` block.
        """
        self.handle_login()
        mock_snap.create_transaction.side_effect = Exception("Midtrans timeout")

        response = self.client.post(
            reverse("transaction"), self._valid_payload(), format="json"
        )

        self.assertEqual(response.status_code, 502)

        self.order.refresh_from_db()
        self.assertTrue(
            OrderShipping.objects.filter(order=self.order).exists()
        )
        self.assertIsNotNone(self.order.shipping)
        mock_logger_error.error.assert_called_once()
    
    @patch("order.views_order_process.logger_error")
    @patch("order.views_order_process.snap")
    @patch("order.services.order.calculate_insurance")
    def test_retry_with_stale_insurance_value_no_longer_causes_permanent_mismatch(
        self, mock_calculate_insurance, mock_snap, mock_logger_error
    ):
        """
        Test: reproduksi skenario bug asli, dengan DB nyata. product_price
        itu IMMUTABLE (tidak bisa berubah), jadi sumber stale-nya BUKAN
        harga produk -- melainkan insurance_value, karena
        calculate_insurance() bergantung field MUTABLE:
        order.store.enable_insurance, order.store.insurance_threshold,
        atau rate/admin_fee di row ShippingInsurance (bisa diubah admin
        kapan saja).

        OrderShippingService TIDAK di-mock -- dia benar-benar jalan
        (create_order_shipping + finalize_order) terhadap DB nyata,
        supaya grand_total dihasilkan oleh calculate_grand_total() yang
        sesungguhnya, bukan angka yang kita karang manual. Yang di-mock
        HANYA calculate_insurance(), untuk merepresentasikan "aturan
        insurance berubah di antara attempt" secara terkontrol.
        """
        self.handle_login()

        # Attempt pertama: buat shipping record awal, calculate_insurance
        # mengembalikan nilai "lama". Midtrans sengaja gagal supaya
        # shipping record tersimpan tapi user perlu retry.
        mock_calculate_insurance.return_value = 5000
        mock_snap.create_transaction.side_effect = Exception("Midtrans timeout")
        
        response_1 = self.client.post(
            reverse("transaction"), self._valid_payload(), format="json"
        )
        
        self.assertEqual(response_1.status_code, 502)

        self.order.refresh_from_db()
        grand_total_attempt_1 = self.order.grand_total
        mock_calculate_insurance.assert_called_once()
        mock_logger_error.error.assert_called_once()

        # Sebelum retry: admin ubah aturan insurance (rate naik).
        mock_calculate_insurance.return_value = 8000
        mock_snap.create_transaction.side_effect = None
        mock_snap.create_transaction.return_value = {"token": "snap-token-recovered"}

        response_2 = self.client.post(
            reverse("transaction"), self._valid_payload(), format="json"
        )

        # Bukti utama: TIDAK stuck di 500/mismatch meski aturan insurance
        # berubah di antara attempt -- karena OrderShippingService selalu
        # di-re-run dan finalize_order() menghitung ulang grand_total
        # secara konsisten dengan item_details yang dipakai untuk validasi.
        self.assertEqual(response_2.status_code, 200)
        self.assertEqual(response_2.data["snap_token"], "snap-token-recovered")
        self.assertEqual(mock_calculate_insurance.call_count, 2)

        self.order.refresh_from_db()
        self.assertNotEqual(self.order.grand_total, grand_total_attempt_1)
        self.assertEqual(self.order.shipping.insurance_value, 8000)
        