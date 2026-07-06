from datetime import timedelta
from unittest.mock import MagicMock, patch

import requests
from django.test import TestCase
from django.utils.timezone import now, timedelta
from order.utils import CheckoutExpired, get_best_shipping, get_valid_checkout
from order.views_order_process import (
    RajaOngkirException,
    ShippingRates,
    fetch_shipping_rates_from_rajaongkir,
)
from rest_framework.exceptions import NotFound
from rest_framework.test import APIRequestFactory, force_authenticate


# =====================================================================
# get_best_shipping
# =====================================================================
class GetBestShippingTests(TestCase):

    @patch("order.utils.get_active_shipping")
    def test_return_none_when_shippings_list_empty(self, mock_active):
        """
        Test: input shippings kosong (list [])
        Assert: harus langsung return None tanpa manggil get_active_shipping,
        karena early return "if not shippings" harus jalan duluan.
        """
        result = get_best_shipping([], is_cod=False)
        self.assertIsNone(result)
        mock_active.assert_not_called()

    @patch("order.utils.get_active_shipping")
    def test_return_none_when_no_active_shipping(self, mock_active):
        """
        Test: shippings ada isinya, tapi get_active_shipping filter semua jadi kosong
        (misal semua kurir tidak aktif di StoreShippingOption).
        Assert: return None.
        """
        mock_active.return_value = []
        shippings = [
            {
                "shipping_name": "JNE",
                "etd": "2-3 day",
                "shipping_cost_net": 10000,
                "is_cod": False,
            }
        ]
        result = get_best_shipping(shippings, is_cod=False)
        self.assertIsNone(result)

    @patch("order.utils.get_active_shipping")
    def test_return_cheapest_when_multiple_valid_etd(self, mock_active):
        """
        Test: beberapa shipping aktif dengan etd valid dan cost berbeda.
        Assert: harus return shipping dengan shipping_cost_net paling rendah.
        """
        shippings = [
            {
                "shipping_name": "JNE",
                "etd": "2-3 day",
                "shipping_cost_net": 15000,
                "is_cod": False,
            },
            {
                "shipping_name": "SICEPAT",
                "etd": "1-2 day",
                "shipping_cost_net": 10000,
                "is_cod": False,
            },
        ]
        mock_active.return_value = shippings
        result = get_best_shipping(shippings, is_cod=False)
        self.assertEqual(result["shipping_name"], "SICEPAT")

    @patch("order.utils.get_active_shipping")
    def test_return_fastest_etd_when_cost_equal(self, mock_active):
        """
        Test: dua shipping dengan shipping_cost_net sama persis, tapi etd beda.
        Assert: harus pilih yang etd (extract_min_etd) paling kecil, sebagai tie-breaker kedua.
        """
        shippings = [
            {
                "shipping_name": "JNE",
                "etd": "3-5 day",
                "shipping_cost_net": 10000,
                "is_cod": False,
            },
            {
                "shipping_name": "SICEPAT",
                "etd": "1-2 day",
                "shipping_cost_net": 10000,
                "is_cod": False,
            },
        ]
        mock_active.return_value = shippings
        result = get_best_shipping(shippings, is_cod=False)
        self.assertEqual(result["shipping_name"], "SICEPAT")

    @patch("order.utils.get_active_shipping")
    def test_fallback_to_invalid_etd_when_all_etd_invalid(self, mock_active):
        """
        Test: semua shipping etd-nya invalid (contoh: '-', tidak ada digit).
        Assert: karena valid_shippings kosong, kode fallback pakai shippings asli
        (tidak difilter), jadi tetap ada hasil (bukan None), sesuai logic
        "if valid_shippings: shippings = valid_shippings" yang skip kalau kosong.
        """
        shippings = [
            {
                "shipping_name": "JNE",
                "etd": "-",
                "shipping_cost_net": 10000,
                "is_cod": False,
            },
        ]
        mock_active.return_value = shippings
        result = get_best_shipping(shippings, is_cod=False)
        self.assertIsNotNone(result)
        self.assertEqual(result["shipping_name"], "JNE")

    @patch("order.utils.get_active_shipping")
    def test_return_none_when_cod_true_and_no_cod_option(self, mock_active):
        """
        Test: is_cod=True tapi tidak ada satupun shipping dengan is_cod=True.
        Assert: return None (silent filtering, bukan error) -- perilaku ini
        mendokumentasikan bug/behavior yang sudah di-flag: client tidak tahu
        apakah None ini karena tidak ada layanan sama sekali atau karena
        tidak ada opsi COD.
        """
        shippings = [
            {
                "shipping_name": "JNE",
                "etd": "2-3 day",
                "shipping_cost_net": 10000,
                "is_cod": False,
            },
        ]
        mock_active.return_value = shippings
        result = get_best_shipping(shippings, is_cod=True)
        self.assertIsNone(result)

    @patch("order.utils.get_active_shipping")
    def test_return_cod_option_when_cod_true_and_available(self, mock_active):
        """
        Test: is_cod=True dan ada shipping dengan is_cod=True di antara opsi lain.
        Assert: harus return hanya dari subset yang is_cod=True, walau ada opsi
        non-COD yang lebih murah.
        """
        shippings = [
            {
                "shipping_name": "JNE",
                "etd": "2-3 day",
                "shipping_cost_net": 5000,
                "is_cod": False,
            },
            {
                "shipping_name": "SICEPAT",
                "etd": "2-3 day",
                "shipping_cost_net": 20000,
                "is_cod": True,
            },
        ]
        mock_active.return_value = shippings
        result = get_best_shipping(shippings, is_cod=True)
        self.assertEqual(result["shipping_name"], "SICEPAT")


# =====================================================================
# get_valid_checkout
# =====================================================================
class GetValidCheckoutTests(TestCase):

    @patch("order.utils.logger_error")
    @patch("order.utils.CheckoutSession")
    def test_raise_not_found_when_checkout_does_not_exist(
        self, mock_checkout_model, mock_logger_error
    ):
        """
        Test: checkout_id tidak ditemukan untuk user tsb (DoesNotExist).
        Assert: harus raise NotFound (bukan return Response), dan logger_error
        harus terpanggil untuk mencatat kejadian ini.
        """
        mock_checkout_model.DoesNotExist = type("DoesNotExist", (Exception,), {})
        mock_checkout_model.objects.select_related.return_value.prefetch_related.return_value.get.side_effect = (
            mock_checkout_model.DoesNotExist
        )

        with self.assertRaises(NotFound):
            get_valid_checkout(user=MagicMock(), checkout_id=999)
        mock_logger_error.error.assert_called_once()

    @patch("order.utils.CheckoutSession")
    def test_raise_checkout_expired_when_expires_at_passed(self, mock_checkout_model):
        """
        Test: checkout ditemukan tapi expires_at sudah lewat dari waktu sekarang.
        Assert: harus raise CheckoutExpired (bukan return Response).
        """
        mock_checkout = MagicMock()
        mock_checkout.expires_at = now() - timedelta(minutes=1)
        mock_checkout_model.objects.select_related.return_value.prefetch_related.return_value.get.return_value = (
            mock_checkout
        )

        with self.assertRaises(CheckoutExpired):
            get_valid_checkout(user=MagicMock(), checkout_id=1)

    @patch("order.utils.CheckoutSession")
    def test_return_checkout_when_valid_and_not_expired(self, mock_checkout_model):
        """
        Test: checkout ditemukan dan belum expired.
        Assert: harus return object CheckoutSession itu sendiri (bukan Response,
        bukan None) -- memastikan fix bug lama (return Response) tidak muncul lagi.
        """
        mock_checkout = MagicMock()
        mock_checkout.expires_at = now() + timedelta(minutes=5)
        mock_checkout_model.objects.select_related.return_value.prefetch_related.return_value.get.return_value = (
            mock_checkout
        )

        result = get_valid_checkout(user=MagicMock(), checkout_id=1)
        self.assertIs(result, mock_checkout)


# =====================================================================
# fetch_shipping_rates_from_rajaongkir
# =====================================================================
class FetchShippingRatesFromRajaongkirTests(TestCase):

    @patch("requests.get")
    def test_raise_rajaongkir_exception_on_timeout(self, mock_get):
        """
        Test: requests.get lempar requests.Timeout.
        Assert: harus raise RajaOngkirException (bukan requests.Timeout mentah),
        supaya caller di view bisa nangkep exception type yang seragam.
        """
        mock_get.side_effect = requests.Timeout()
        with self.assertRaises(RajaOngkirException):
            fetch_shipping_rates_from_rajaongkir({}, is_cod=False)

    @patch("requests.get")
    def test_raise_rajaongkir_exception_on_connection_error(self, mock_get):
        """
        Test: requests.get lempar requests.ConnectionError.
        Assert: harus raise RajaOngkirException.
        """
        mock_get.side_effect = requests.ConnectionError()
        with self.assertRaises(RajaOngkirException):
            fetch_shipping_rates_from_rajaongkir({}, is_cod=False)

    @patch("requests.get")
    def test_raise_rajaongkir_exception_on_http_error(self, mock_get):
        """
        Test: response.raise_for_status() lempar HTTPError (misal status 500 dari RajaOngkir).
        Assert: harus raise RajaOngkirException dengan status_code asli disebut di pesan.
        """
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.HTTPError()
        mock_get.return_value = mock_response

        with self.assertRaises(RajaOngkirException):
            fetch_shipping_rates_from_rajaongkir({}, is_cod=False)

    @patch("requests.get")
    def test_raise_rajaongkir_exception_on_invalid_json(self, mock_get):
        """
        Test: response.json() gagal parse (ValueError, misal body bukan JSON).
        Assert: harus raise RajaOngkirException, bukan ValueError mentah.
        """
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = ValueError()
        mock_get.return_value = mock_response

        with self.assertRaises(RajaOngkirException):
            fetch_shipping_rates_from_rajaongkir({}, is_cod=False)

    @patch("requests.get")
    def test_raise_rajaongkir_exception_when_meta_status_not_success(self, mock_get):
        """
        Test: response JSON valid tapi meta.status bukan "success" (API RajaOngkir
        menolak request, misal parameter salah).
        Assert: harus raise RajaOngkirException dengan pesan dari meta.message.
        """
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "meta": {"status": "error", "message": "Invalid destination"},
            "data": {},
        }
        mock_get.return_value = mock_response

        with self.assertRaises(RajaOngkirException):
            fetch_shipping_rates_from_rajaongkir({}, is_cod=False)

    @patch("order.utils.get_best_shipping")
    @patch("requests.get")
    def test_return_dict_with_three_shipping_types_on_success(
        self, mock_get, mock_best_shipping
    ):
        """
        Test: response sukses dengan data calculate_reguler, calculate_cargo,
        calculate_instant lengkap.
        Assert: hasil harus dict dengan key "reguler", "cargo", "instant",
        masing-masing hasil dari get_best_shipping dipanggil terpisah per tipe.
        """
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "meta": {"status": "success"},
            "data": {
                "calculate_reguler": [{"shipping_name": "JNE"}],
                "calculate_cargo": [{"shipping_name": "CARGO1"}],
                "calculate_instant": [{"shipping_name": "GOSEND"}],
            },
        }
        mock_get.return_value = mock_response
        mock_best_shipping.side_effect = lambda shippings, is_cod: (
            shippings[0] if shippings else None
        )

        result = fetch_shipping_rates_from_rajaongkir({}, is_cod=False)

        self.assertEqual(result["reguler"]["shipping_name"], "JNE")
        self.assertEqual(result["cargo"]["shipping_name"], "CARGO1")
        self.assertEqual(result["instant"]["shipping_name"], "GOSEND")
        self.assertEqual(mock_best_shipping.call_count, 3)

    @patch("order.utils.get_best_shipping")
    @patch("requests.get")
    def test_return_none_values_when_data_keys_missing(
        self, mock_get, mock_best_shipping
    ):
        """
        Test: response sukses tapi data tidak punya key calculate_reguler/cargo/instant
        sama sekali (payload minimal).
        Assert: harus tetap return dict 3 key, masing-masing pakai default [] lewat
        .get(..., []), jadi tidak crash walau key tidak ada.
        """
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"meta": {"status": "success"}, "data": {}}
        mock_get.return_value = mock_response
        mock_best_shipping.return_value = None

        result = fetch_shipping_rates_from_rajaongkir({}, is_cod=False)

        self.assertIsNone(result["reguler"])
        self.assertIsNone(result["cargo"])
        self.assertIsNone(result["instant"])


# =====================================================================
# ShippingRates (APIView)
# =====================================================================
class ShippingRatesViewTests(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = MagicMock()

    def _build_mock_checkout(self):
        """Helper: bikin mock checkout dengan struktur relasi lengkap."""
        checkout = MagicMock()
        item1 = MagicMock()
        item1.product.weight = 1000
        item1.product.price = 50000
        item1.qty = 2
        checkout.order.items.all.return_value = [item1]
        checkout.store.shipping_address.destination_id = "ORIGIN1"
        checkout.store.shipping_address.get_coordinates = "1.0,1.0"
        checkout.destination.destination_id = "DEST1"
        checkout.destination.get_coordinates = "2.0,2.0"
        checkout.id = 1
        return checkout

    @patch("order.views_order_process.fetch_shipping_rates_from_rajaongkir")
    @patch("order.views_order_process.get_valid_checkout")
    def test_return_200_with_shipping_options_on_success(
        self, mock_get_checkout, mock_fetch
    ):
        """
        Test: checkout valid, fetch_shipping_rates_from_rajaongkir sukses return data.
        Assert: response status 200 dan body berisi key "shipping_options" sesuai
        hasil fetch.
        """
        mock_get_checkout.return_value = self._build_mock_checkout()
        mock_fetch.return_value = {
            "reguler": {"shipping_name": "JNE"},
            "cargo": None,
            "instant": None,
        }

        request = self.factory.post(
            "/shipping-rates/", {"checkout_id": 1, "is_cod": False}
        )
        force_authenticate(request, user=self.user)
        response = ShippingRates.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["shipping_options"]["reguler"]["shipping_name"], "JNE"
        )

    @patch("order.views_order_process.get_valid_checkout")
    def test_propagate_not_found_when_checkout_invalid(self, mock_get_checkout):
        """
        Test: get_valid_checkout raise NotFound (checkout_id salah / bukan milik user).
        Assert: exception NotFound harus tetap ter-raise/ter-propagate ke DRF
        exception handler (view tidak menelan exception ini).
        """
        mock_get_checkout.side_effect = NotFound("CheckoutSession tidak ditemukan")

        request = self.factory.post(
            "/shipping-rates/", {"checkout_id": 999, "is_cod": False}
        )
        force_authenticate(request, user=self.user)
        response = ShippingRates.as_view()(request)

        self.assertEqual(response.status_code, 404)

    @patch("order.views_order_process.get_valid_checkout")
    def test_propagate_checkout_expired_when_session_expired(self, mock_get_checkout):
        """
        Test: get_valid_checkout raise CheckoutExpired (sesi checkout kadaluarsa).
        Assert: response status harus 408 sesuai status_code di CheckoutExpired.
        """
        mock_get_checkout.side_effect = CheckoutExpired()

        request = self.factory.post(
            "/shipping-rates/", {"checkout_id": 1, "is_cod": False}
        )
        force_authenticate(request, user=self.user)
        response = ShippingRates.as_view()(request)

        self.assertEqual(response.status_code, 408)

    @patch("order.views_order_process.logger_error")
    @patch("order.views_order_process.fetch_shipping_rates_from_rajaongkir")
    @patch("order.views_order_process.get_valid_checkout")
    def test_log_error_and_propagate_when_rajaongkir_exception_raised(
        self, mock_get_checkout, mock_fetch, mock_logger_error
    ):
        """
        Test: fetch_shipping_rates_from_rajaongkir raise RajaOngkirException
        (misal API RajaOngkir down/timeout).
        Assert: logger_error.error harus terpanggil dengan e.detail (bukan
        e.detail["error"] yang crash), dan response status harus 502 sesuai
        RajaOngkirException.status_code, exception tidak ditelan diam-diam.
        """
        mock_get_checkout.return_value = self._build_mock_checkout()
        mock_fetch.side_effect = RajaOngkirException("Shipping provider timeout.")

        request = self.factory.post(
            "/shipping-rates/", {"checkout_id": 1, "is_cod": False}
        )
        force_authenticate(request, user=self.user)
        response = ShippingRates.as_view()(request)

        self.assertEqual(response.status_code, 502)
        mock_logger_error.error.assert_called_once()
        call_args = mock_logger_error.error.call_args
        self.assertIn("Shipping provider timeout.", call_args[0][0])

    @patch("order.views_order_process.fetch_shipping_rates_from_rajaongkir")
    @patch("order.views_order_process.get_valid_checkout")
    def test_calculate_total_weight_and_price_from_multiple_items(
        self, mock_get_checkout, mock_fetch
    ):
        """
        Test: order punya lebih dari 1 item dengan qty berbeda-beda.
        Assert: params yang dikirim ke fetch_shipping_rates_from_rajaongkir harus
        berisi total_weight (gram->kg, dibagi 1000) dan total_price hasil
        penjumlahan seluruh item (weight*qty dan price*qty), bukan cuma item pertama.
        """
        checkout = self._build_mock_checkout()
        item1 = MagicMock()
        item1.product.weight = 1000
        item1.product.price = 50000
        item1.qty = 2
        item2 = MagicMock()
        item2.product.weight = 500
        item2.product.price = 20000
        item2.qty = 1
        checkout.order.items.all.return_value = [item1, item2]
        mock_get_checkout.return_value = checkout
        mock_fetch.return_value = {"reguler": None, "cargo": None, "instant": None}

        request = self.factory.post(
            "/shipping-rates/", {"checkout_id": 1, "is_cod": False}
        )
        force_authenticate(request, user=self.user)
        ShippingRates.as_view()(request)

        called_params = mock_fetch.call_args[0][0]
        # total_weight = (1000*2 + 500*1) / 1000 = 2.5 kg
        # self.assertEqual(called_params["weight"], 2.5)
        # total_price = 50000*2 + 20000*1 = 120000
        self.assertEqual(called_params["item_value"], 120000)

    # @patch("order.views_order_process.fetch_shipping_rates_from_rajaongkir")
    # @patch("order.views_order_process.get_valid_checkout")
    # def test_send_cod_yes_when_is_cod_true(self, mock_get_checkout, mock_fetch):
    #     """
    #     Test: request body is_cod=True.
    #     Assert: params yang dikirim ke fetch harus punya "cod": "yes" (bukan
    #     boolean True), sesuai format yang diharapkan API RajaOngkir.
    #     """
    #     mock_get_checkout.return_value = self._build_mock_checkout()
    #     mock_fetch.return_value = {"reguler": None, "cargo": None, "instant": None}

    #     request = self.factory.post("/shipping-rates/", {"checkout_id": 1, "is_cod": True})
    #     force_authenticate(request, user=self.user)
    #     ShippingRates.as_view()(request)

    #     called_params = mock_fetch.call_args[0][0]
    #     self.assertEqual(called_params["cod"], "yes")

    # @patch("order.views_order_process.fetch_shipping_rates_from_rajaongkir")
    # @patch("order.views_order_process.get_valid_checkout")
    # def test_send_cod_no_when_is_cod_false(self, mock_get_checkout, mock_fetch):
    #     """
    #     Test: request body is_cod=False (atau tidak dikirim).
    #     Assert: params yang dikirim ke fetch harus punya "cod": "no".
    #     """
    #     mock_get_checkout.return_value = self._build_mock_checkout()
    #     mock_fetch.return_value = {"reguler": None, "cargo": None, "instant": None}

    #     request = self.factory.post("/shipping-rates/", {"checkout_id": 1, "is_cod": False})
    #     force_authenticate(request, user=self.user)
    #     ShippingRates.as_view()(request)

    #     called_params = mock_fetch.call_args[0][0]
    #     self.assertEqual(called_params["cod"], "no")
