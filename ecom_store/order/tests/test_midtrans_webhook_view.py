import json
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from order.models import Order
from order.services.midtrans import InvalidMidtransPayload, InvalidMidtransSignature
from rest_framework.test import APIClient


class MidtransWebhookViewTests(TestCase):
    """
    Integration test untuk MidtransWebhookView. WebhookMidtrans di-mock total
    di level view -- test ini HANYA menguji alur/wiring view (response code,
    method mana yang terpanggil sesuai kondisi, exception handling), BUKAN
    logic internal WebhookMidtrans (sudah dites di test_midtrans_webhook.py).
    """

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("midtrans_webhook")

        self.logger_patcher = patch("order.views_order_process.logger")
        self.mock_logger = self.logger_patcher.start()
        self.addCleanup(self.logger_patcher.stop)

    def _post(self, body=b'{"order_id": "ORDER-1"}'):
        return self.client.post(self.url, data=body, content_type="application/json")

    @patch("order.views_order_process.WebhookMidtrans")
    def test_invalid_signature_returns_403(self, mock_webhook_class):
        """
        Test: validate_signature raise InvalidMidtransSignature.
        Assert: response 403, get_order() dan seterusnya TIDAK terpanggil.
        """
        mock_instance = mock_webhook_class.return_value
        mock_instance.validate_signature.side_effect = InvalidMidtransSignature(
            "Invalid Midtrans signature"
        )

        response = self._post()

        self.assertEqual(response.status_code, 403)
        mock_instance.get_order.assert_not_called()

    @patch("order.views_order_process.WebhookMidtrans")
    def test_invalid_payload_returns_400(self, mock_webhook_class):
        """
        Test: validate_signature raise InvalidMidtransPayload (JSON rusak).
        Assert: response 400, get_order() TIDAK terpanggil.
        """
        mock_instance = mock_webhook_class.return_value
        mock_instance.validate_signature.side_effect = InvalidMidtransPayload(
            "Invalid JSON payload"
        )

        response = self._post()

        self.assertEqual(response.status_code, 400)
        mock_instance.get_order.assert_not_called()

    @patch("order.views_order_process.WebhookMidtrans")
    def test_order_does_not_exist_returns_404(self, mock_webhook_class):
        """
        Test: get_order() raise Order.DoesNotExist.
        Assert: response 404, change_payment_status_order() TIDAK terpanggil.
        """
        mock_instance = mock_webhook_class.return_value
        mock_instance.validate_signature.return_value = {"order_id": "ORDER-1"}
        mock_instance.get_order.side_effect = Order.DoesNotExist

        response = self._post()

        self.assertEqual(response.status_code, 404)
        mock_instance.change_payment_status_order.assert_not_called()

    @patch("order.views_order_process.WebhookMidtrans")
    def test_order_validation_error_returns_404(self, mock_webhook_class):
        """
        Test: get_order() raise ValidationError (format order_id tidak valid).
        Assert: response 404.
        """
        mock_instance = mock_webhook_class.return_value
        mock_instance.validate_signature.return_value = {"order_id": "bad-id"}
        mock_instance.get_order.side_effect = ValidationError("invalid format")

        response = self._post()

        self.assertEqual(response.status_code, 404)

    @patch("order.views_order_process.logger_error")
    @patch("order.views_order_process.WebhookMidtrans")
    def test_change_payment_status_generic_exception_returns_500(
        self, mock_webhook_class, mock_logger_error
    ):
        """
        Test: change_payment_status_order() raise exception tak terduga
        (bug/error internal lain di luar DoesNotExist/ValidationError).
        Assert: response 500, error ter-log, reduce_stock/reverse_stock
        TIDAK terpanggil.
        """
        mock_instance = mock_webhook_class.return_value
        mock_instance.validate_signature.return_value = {"order_id": "ORDER-1"}
        mock_instance.change_payment_status_order.side_effect = Exception(
            "unexpected error"
        )

        response = self._post()

        self.assertEqual(response.status_code, 500)
        mock_logger_error.error.assert_called_once()
        mock_instance.reduce_stock.assert_not_called()
        mock_instance.reverse_stock.assert_not_called()

    @patch("order.views_order_process.WebhookMidtrans")
    def test_is_paid_true_calls_reduce_stock_not_reverse_stock(
        self, mock_webhook_class
    ):
        """
        Test: change_payment_status_order() return True (is_paid).
        Assert: reduce_stock() terpanggil, reverse_stock() TIDAK terpanggil,
        response 200.
        """
        mock_instance = mock_webhook_class.return_value
        mock_instance.validate_signature.return_value = {"order_id": "ORDER-1"}
        mock_instance.change_payment_status_order.return_value = True

        response = self._post()

        self.assertEqual(response.status_code, 200)
        mock_instance.reduce_stock.assert_called_once()
        mock_instance.reverse_stock.assert_not_called()

    @patch("order.views_order_process.WebhookMidtrans")
    def test_is_paid_false_calls_reverse_stock_not_reduce_stock(
        self, mock_webhook_class
    ):
        """
        Test: change_payment_status_order() return False (bukan/tidak lagi
        paid -- termasuk kasus reversal maupun failed biasa).
        Assert: reverse_stock() terpanggil, reduce_stock() TIDAK terpanggil,
        response 200.
        """
        mock_instance = mock_webhook_class.return_value
        mock_instance.validate_signature.return_value = {"order_id": "ORDER-1"}
        mock_instance.change_payment_status_order.return_value = False

        response = self._post()

        self.assertEqual(response.status_code, 200)
        mock_instance.reverse_stock.assert_called_once()
        mock_instance.reduce_stock.assert_not_called()

    @patch("order.views_order_process.logger_error")
    @patch("order.views_order_process.WebhookMidtrans")
    def test_reduce_stock_exception_returns_500(
        self, mock_webhook_class, mock_logger_error
    ):
        """
        Test: is_paid True, tapi reduce_stock() raise exception (misal stok
        tidak cukup atau DB error).
        Assert: response 500, critical logged untuk manual review.
        payment_status TIDAK di-rollback (blok atomic terpisah, sudah
        ter-commit di langkah sebelumnya -- ini adalah keputusan desain,
        bukan diverifikasi ulang di sini karena DB di-mock).
        """
        mock_instance = mock_webhook_class.return_value
        mock_instance.validate_signature.return_value = {"order_id": "ORDER-1"}
        mock_instance.change_payment_status_order.return_value = True
        mock_instance.reduce_stock.side_effect = Exception("stok tidak cukup")
        mock_instance.order.order_id = "ORDER-1"

        response = self._post()

        self.assertEqual(response.status_code, 500)
        mock_logger_error.critical.assert_called_once()

    @patch("order.views_order_process.logger_error")
    @patch("order.views_order_process.WebhookMidtrans")
    def test_reverse_stock_exception_returns_500(
        self, mock_webhook_class, mock_logger_error
    ):
        """
        Test: is_paid False, tapi reverse_stock() raise exception.
        Assert: response 500, critical logged untuk manual review.
        """
        mock_instance = mock_webhook_class.return_value
        mock_instance.validate_signature.return_value = {"order_id": "ORDER-1"}
        mock_instance.change_payment_status_order.return_value = False
        mock_instance.reverse_stock.side_effect = Exception("DB error")
        mock_instance.order.order_id = "ORDER-1"

        response = self._post()

        self.assertEqual(response.status_code, 500)
        mock_logger_error.critical.assert_called_once()

    @patch("order.views_order_process.WebhookMidtrans")
    def test_new_failed_transition_calls_release_reservation(self, mock_webhook_class):
        """
        Test: is_paid False, old_status "pending", new_status "failed"
        (transisi BARU menuju failed, bukan reversal dan bukan duplikat).
        Assert: release_reservation() terpanggil, response 200.
        """
        mock_instance = mock_webhook_class.return_value
        mock_instance.validate_signature.return_value = {"order_id": "ORDER-1"}
        mock_instance.change_payment_status_order.return_value = False
        mock_instance.old_status = "pending"
        mock_instance.new_status = "failed"
        mock_instance.order.order_id = "ORDER-1"

        response = self._post()

        self.assertEqual(response.status_code, 200)
        mock_instance.release_reservation.assert_called_once()

    @patch("order.views_order_process.WebhookMidtrans")
    def test_reversal_does_not_call_release_reservation(self, mock_webhook_class):
        """
        Test: is_paid False, old_status "paid", new_status "failed" (reversal,
        reservasi sudah closed sejak dulu oleh reduce_stock).
        Assert: release_reservation() TIDAK terpanggil, reverse_stock() tetap
        terpanggil, response 200.
        """
        mock_instance = mock_webhook_class.return_value
        mock_instance.validate_signature.return_value = {"order_id": "ORDER-1"}
        mock_instance.change_payment_status_order.return_value = False
        mock_instance.old_status = "paid"
        mock_instance.new_status = "failed"
        mock_instance.order.order_id = "ORDER-1"

        response = self._post()

        self.assertEqual(response.status_code, 200)
        mock_instance.reverse_stock.assert_called_once()
        mock_instance.release_reservation.assert_not_called()

    @patch("order.views_order_process.WebhookMidtrans")
    def test_duplicate_failed_does_not_call_release_reservation(
        self, mock_webhook_class
    ):
        """
        Test: is_paid False, old_status "failed", new_status "failed"
        (webhook duplikat untuk order yang sudah failed sebelumnya).
        Assert: release_reservation() TIDAK terpanggil, response 200.
        """
        mock_instance = mock_webhook_class.return_value
        mock_instance.validate_signature.return_value = {"order_id": "ORDER-1"}
        mock_instance.change_payment_status_order.return_value = False
        mock_instance.old_status = "failed"
        mock_instance.new_status = "failed"
        mock_instance.order.order_id = "ORDER-1"

        response = self._post()

        self.assertEqual(response.status_code, 200)
        mock_instance.release_reservation.assert_not_called()

    @patch("order.views_order_process.logger_error")
    @patch("order.views_order_process.WebhookMidtrans")
    def test_release_reservation_exception_returns_500(
        self, mock_webhook_class, mock_logger_error
    ):
        """
        Test: is_paid False, old_status "pending", new_status "failed" (harus
        panggil release_reservation), tapi release_reservation() raise exception.
        Assert: response 500, critical logged.
        """
        mock_instance = mock_webhook_class.return_value
        mock_instance.validate_signature.return_value = {"order_id": "ORDER-1"}
        mock_instance.change_payment_status_order.return_value = False
        mock_instance.old_status = "pending"
        mock_instance.new_status = "failed"
        mock_instance.order.order_id = "ORDER-1"
        mock_instance.release_reservation.side_effect = Exception("DB error")

        response = self._post()

        self.assertEqual(response.status_code, 500)
        mock_logger_error.critical.assert_called_once()

    @patch("order.views_order_process.WebhookMidtrans")
    def test_pending_transaction_status_does_not_call_release_reservation(
        self, mock_webhook_class
    ):
        """
        Test: webhook transaction_status "pending" (customer baru buat kode
        bayar, belum ada keputusan final) -- is_paid False, TAPI new_status
        TETAP "pending" (tidak ada transisi status sama sekali). Ini celah
        yang sempat ditemukan: old_status "pending" juga "not in (paid,
        failed)", tapi TIDAK boleh memicu release_reservation() karena order
        belum benar-benar gagal, cuma informational.
        Assert: release_reservation() TIDAK terpanggil, reserved_stock tidak
        boleh dilepas prematur.
        """
        mock_instance = mock_webhook_class.return_value
        mock_instance.validate_signature.return_value = {"order_id": "ORDER-1"}
        mock_instance.change_payment_status_order.return_value = False
        mock_instance.old_status = "pending"
        mock_instance.new_status = "pending"  # tidak berubah
        mock_instance.order.order_id = "ORDER-1"

        response = self._post()

        self.assertEqual(response.status_code, 200)
        mock_instance.release_reservation.assert_not_called()
