from datetime import timedelta
from unittest.mock import MagicMock, patch

from cart.models import Cart
from django.core.management import call_command
from django.test import TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from order.models import CheckoutSession, Order, OrderItem
from product.models import Product
from rest_framework.test import APIClient

from .helper_setup import (
    set_address,
    set_location_fields,
    set_store,
    set_store_shipping_option,
    set_user,
)


class ShippingRatesIntegrationTest(TransactionTestCase):
    """
    Integration test untuk ShippingRates endpoint.

    Tujuan test ini BEDA dari unit test (test_shipping_rates.py):
    unit test membuktikan LOGIC (filtering, error handling, kalkulasi)
    dengan model di-mock. Test ini membuktikan bahwa STRUKTUR model asli
    (relasi FK, nama field) benar-benar nyambung -- karena select_related,
    prefetch_related, dan akses field seperti checkout.store.shipping_address
    tidak pernah benar-benar dieksekusi lawan database asli di unit test.

    Hanya perlu 1-2 skenario di sini (happy path + 1 error path),
    bukan mengulang semua skenario yang sudah di-cover unit test.
    """

    def setUp(self):
        self.client = APIClient()

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

    @patch("accounts.signals.logger")
    @patch("order.views_order_process.logger")
    @patch("order.views_order_process.logger_error")
    @patch("order.utils.logger")
    @patch("order.utils.logger_error")
    @patch("requests.get")
    def test_return_200_with_valid_checkout_using_real_models(
        self,
        mock_requests_get,
        order_logger_error_util,
        order_log_util,
        order_logger_error_view,
        order_log_view,
        mock_logger,
    ):
        """
        Test: checkout dibuat lewat model asli (bukan mock), field/relasi
        (store, destination, order, order_item, product) benar-benar ada
        di database. Yang di-mock cuma requests.get (panggilan network ke
        RajaOngkir) -- seluruh logic sesudahnya (parsing JSON,
        get_best_shipping, get_active_shipping yang query StoreShippingOption
        asli, has_valid_etd, extract_min_etd) BENAR-BENAR JALAN, tidak ada
        yang di-mock di tengah.

        Assert: response 200, dan shipping_options berisi hasil yang
        konsisten dengan data mock RajaOngkir + StoreShippingOption asli
        yang sudah di-set di setUp (lewat set_store_shipping_option).
        Ini juga membuktikan select_related/prefetch_related di
        get_valid_checkout match dengan struktur model asli, karena kalau
        field/relasi salah nama, request akan crash sebelum sampai ke
        assertion manapun.
        """
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "meta": {
                "message": "Success Calculate Shipping",
                "code": 200,
                "status": "success",
            },
            "data": {
                "calculate_reguler": [
                    {
                        "shipping_name": "JNE",
                        "service_name": "CTC23",
                        "weight": 0.5,
                        "is_cod": True,
                        "shipping_cost": 9000,
                        "shipping_cashback": 1800,
                        "shipping_cost_net": 7200,
                        "grandtotal": 19000,
                        "service_fee": 532,
                        "net_income": 11268,
                        "etd": "1-2 day",
                    },
                    {
                        "shipping_name": "SAP",
                        "service_name": "UDRREG",
                        "weight": 0.5,
                        "is_cod": True,
                        "shipping_cost": 10000,
                        "shipping_cashback": 3000,
                        "shipping_cost_net": 7000,
                        "grandtotal": 20000,
                        "service_fee": 560,
                        "net_income": 12440,
                        "etd": "1-3 day",
                    },
                    {
                        "shipping_name": "JNT",
                        "service_name": "EZ",
                        "weight": 0.5,
                        "is_cod": False,
                        "shipping_cost": 7000,
                        "shipping_cashback": 1750,
                        "shipping_cost_net": 5250,
                        "grandtotal": 17000,
                        "service_fee": 476,
                        "net_income": 11274,
                        "etd": "-",
                    },
                    {
                        "shipping_name": "LION",
                        "service_name": "REGPACK",
                        "weight": 0.5,
                        "is_cod": False,
                        "shipping_cost": 7000,
                        "shipping_cashback": 1400,
                        "shipping_cost_net": 5600,
                        "grandtotal": 17000,
                        "service_fee": 476,
                        "net_income": 10924,
                        "etd": "1-3 day",
                    },
                ],
                "calculate_cargo": [],
                "calculate_instant": [
                    {
                        "shipping_name": "GOSEND",
                        "service_name": "Instant",
                        "weight": 0.5,
                        "is_cod": False,
                        "shipping_cost": 10000,
                        "shipping_cashback": 0,
                        "shipping_cost_net": 10000,
                        "grandtotal": 20000,
                        "service_fee": 0,
                        "net_income": 10000,
                        "etd": "1-2 hours",
                    }
                ],
            },
        }
        mock_requests_get.return_value = mock_response

        self.handle_login()

        res = self.client.post(
            reverse("shipping_rates"), data={"checkout_id": self.checkout.id}
        )

        self.assertEqual(res.status_code, 200)

        # calculate_cargo kosong dari RajaOngkir -> get_best_shipping harus
        # return None (early return "if not shippings")
        self.assertIsNone(res.data["shipping_options"]["cargo"])

        # calculate_instant cuma ada GOSEND, tapi GOSEND TIDAK ada di
        # set_store_shipping_option (yang aktif cuma JNE, JNT, SICEPAT).
        # get_active_shipping harus filter GOSEND keluar -> shippings jadi
        # kosong -> get_best_shipping return None.
        self.assertIsNone(res.data["shipping_options"]["instant"])

        # reguler: dari 4 kurir (JNE, SAP, JNT, LION), yang aktif di
        # StoreShippingOption cuma JNE dan JNT (SAP, LION difilter keluar
        # oleh get_active_shipping karena tidak terdaftar).
        # JNT punya etd "-" (invalid, gagal has_valid_etd), jadi
        # valid_shippings cuma berisi JNE -> JNE otomatis menang
        # (satu-satunya kandidat tersisa setelah dua tahap filter).
        reguler = res.data["shipping_options"]["reguler"]
        self.assertIsNotNone(reguler)
        self.assertEqual(reguler["shipping_name"], "JNE")
        self.assertEqual(reguler["shipping_cost_net"], 7200)
        self.assertEqual(reguler["etd"], "1-2 day")

    @patch("accounts.signals.logger")
    @patch("order.views_order_process.logger")
    @patch("order.views_order_process.logger_error")
    @patch("order.utils.logger")
    @patch("order.utils.logger_error")
    def test_return_408_when_checkout_expired_using_real_model(
        self,
        order_logger_error_util,
        order_log_util,
        order_logger_error_view,
        order_log_view,
        mock_logger,
    ):
        """
        Test: checkout asli di database tapi expires_at sudah lewat.
        Assert: response 408 (CheckoutExpired), membuktikan pengecekan
        now() >= checkout.expires_at bekerja benar terhadap datetime asli
        dari database (bukan MagicMock datetime seperti di unit test).
        """
        self.checkout.expires_at = timezone.now() - timedelta(minutes=1)
        self.checkout.save()

        self.handle_login()

        res = self.client.post(
            reverse("shipping_rates"), data={"checkout_id": self.checkout.id}
        )

        self.assertEqual(res.status_code, 408)
