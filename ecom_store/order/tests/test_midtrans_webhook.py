import hashlib
import json
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import TestCase
from order.models import Order
from order.services.midtrans import (
    InvalidMidtransPayload,
    InvalidMidtransSignature,
    WebhookMidtrans,
)


# =====================================================================
# get_order
# =====================================================================
class GetOrderTests(TestCase):

    @patch("order.services.midtrans.Order")
    def test_get_order_sets_order_on_success(self, mock_order_model):
        """
        Test: order_id di payload cocok dengan order yang ada di DB.
        Assert: self.order ke-set dari hasil query, chain
        select_for_update().prefetch_related().get() terpanggil dengan
        order_id yang benar dari payload.
        """
        mock_order_instance = MagicMock()
        mock_queryset = mock_order_model.objects.select_for_update.return_value
        mock_queryset.prefetch_related.return_value.get.return_value = (
            mock_order_instance
        )

        webhook = WebhookMidtrans()
        webhook.payload = {"order_id": "ORDER-123"}

        webhook.get_order()

        self.assertEqual(webhook.order, mock_order_instance)
        mock_order_model.objects.select_for_update.assert_called_once()
        mock_queryset.prefetch_related.assert_called_once_with("items__product")
        mock_queryset.prefetch_related.return_value.get.assert_called_once_with(
            order_id="ORDER-123"
        )

    @patch("order.services.midtrans.logger_error")
    @patch("order.services.midtrans.Order.objects")
    def test_get_order_raises_does_not_exist(self, mock_order_model, mock_logger_error):
        """
        Test: order_id di payload tidak cocok dengan order manapun di DB.
        Assert: Order.DoesNotExist ter-raise (tidak ditelan), error ter-log.
        """
        mock_queryset = mock_order_model.select_for_update.return_value
        mock_queryset.prefetch_related.return_value.get.side_effect = Order.DoesNotExist

        webhook = WebhookMidtrans()
        webhook.payload = {"order_id": "ORDER-NOT-FOUND"}

        with self.assertRaises(Order.DoesNotExist):
            webhook.get_order()

        mock_logger_error.error.assert_called_once()

    @patch("order.services.midtrans.logger_error")
    @patch("order.services.midtrans.Order.objects")
    def test_get_order_raises_validation_error(
        self, mock_order_model, mock_logger_error
    ):
        """
        Test: order_id di payload bukan format valid (misal bukan UUID kalau
        field order_id memakai UUID sebagai primary/lookup key).
        Assert: ValidationError ter-raise (tidak ditelan), error ter-log.
        """
        mock_queryset = mock_order_model.select_for_update.return_value
        mock_queryset.prefetch_related.return_value.get.side_effect = ValidationError(
            "invalid order_id format"
        )

        webhook = WebhookMidtrans()
        webhook.payload = {"order_id": "not-a-valid-id"}

        with self.assertRaises(ValidationError):
            webhook.get_order()

        mock_logger_error.error.assert_called_once()


# =====================================================================
# change_payment_status_order
# =====================================================================
class ChangePaymentStatusOrderTests(TestCase):

    def _build_webhook(self, payload, current_status):
        webhook = WebhookMidtrans()
        webhook.payload = payload
        webhook.order = MagicMock()
        webhook.order.payment_status = current_status
        return webhook

    def test_pending_to_paid_when_settlement_and_fraud_status_none(self):
        """
        Test: transaction_status settlement, fraud_status tidak dikirim (None) --
        kasus nyata untuk metode non-kartu (QRIS, bank transfer, dsb) yang tidak
        dievaluasi Fraud Detection System.
        Assert: payment_status jadi paid, save() terpanggil, return True.
        """
        payload = {"transaction_status": "settlement", "fraud_status": None}
        webhook = self._build_webhook(payload, current_status="pending")

        result = webhook.change_payment_status_order()

        self.assertTrue(result)
        self.assertEqual(webhook.order.payment_status, "paid")
        webhook.order.save.assert_called_once_with(update_fields=["payment_status"])

    def test_pending_to_paid_when_settlement_and_fraud_status_accept(self):
        """
        Test: transaction_status settlement, fraud_status "accept" (kartu, fraud
        check lolos).
        Assert: payment_status jadi paid, return True.
        """
        payload = {"transaction_status": "settlement", "fraud_status": "accept"}
        webhook = self._build_webhook(payload, current_status="pending")

        result = webhook.change_payment_status_order()

        self.assertTrue(result)
        self.assertEqual(webhook.order.payment_status, "paid")

    def test_pending_to_failed_when_settlement_and_fraud_status_deny(self):
        """
        Test: transaction_status settlement/capture tapi fraud_status "deny"
        (kartu, fraud check gagal).
        Assert: payment_status jadi failed, bukan paid. return False.
        """
        payload = {"transaction_status": "capture", "fraud_status": "deny"}
        webhook = self._build_webhook(payload, current_status="pending")

        result = webhook.change_payment_status_order()

        self.assertFalse(result)
        self.assertEqual(webhook.order.payment_status, "failed")

    def test_pending_to_failed_when_deny_cancel_or_expire(self):
        """
        Test: transaction_status deny/cancel/expire (pembayaran tidak pernah
        berhasil, bukan reversal).
        Assert: payment_status jadi failed untuk masing-masing status ini.
        """
        for status in ["deny", "cancel", "expire"]:
            with self.subTest(transaction_status=status):
                payload = {"transaction_status": status, "fraud_status": None}
                webhook = self._build_webhook(payload, current_status="pending")

                result = webhook.change_payment_status_order()

                self.assertFalse(result)
                self.assertEqual(webhook.order.payment_status, "failed")

    def test_paid_to_failed_on_reversal(self):
        """
        Test: order sudah paid, Midtrans kirim reversal (transaction_status deny)
        -- kasus nyata untuk Permata/Mandiri Bill Payment/Indomaret yang bisa
        settlement lalu deny dalam 1-5 menit.
        Assert: payment_status berubah jadi failed (transisi diizinkan), return False.
        """
        payload = {"transaction_status": "deny", "fraud_status": None}
        webhook = self._build_webhook(payload, current_status="paid")

        result = webhook.change_payment_status_order()

        self.assertFalse(result)
        self.assertEqual(webhook.order.payment_status, "failed")
        self.assertEqual(webhook.old_status, "paid")
        webhook.order.save.assert_called_once_with(update_fields=["payment_status"])

    @patch("order.services.midtrans.logger_error")
    def test_failed_to_paid_is_blocked(self, mock_logger_error):
        """
        Test: order sudah failed, webhook lain (retry/telat) datang dengan
        transaction_status settlement -- transisi failed -> paid tidak boleh
        terjadi (final state, tidak pernah didokumentasikan Midtrans sebagai
        arah reversal yang valid).
        Assert: payment_status TETAP failed, save() tidak dipanggil untuk
        mengubah status, return False, dan warning ter-log.
        """
        payload = {"transaction_status": "settlement", "fraud_status": "accept"}
        webhook = self._build_webhook(payload, current_status="failed")

        result = webhook.change_payment_status_order()

        self.assertFalse(result)
        self.assertEqual(webhook.order.payment_status, "failed")
        webhook.order.save.assert_not_called()
        mock_logger_error.warning.assert_called_once()

    def test_paid_to_paid_duplicate_webhook_is_noop(self):
        """
        Test: order sudah paid, webhook duplikat datang lagi dengan
        transaction_status settlement (Midtrans retry meski sudah 200 diterima).
        Assert: tidak ada perubahan status, save() TIDAK dipanggil lagi
        (hindari write DB yang tidak perlu), return True.
        """
        payload = {"transaction_status": "settlement", "fraud_status": "accept"}
        webhook = self._build_webhook(payload, current_status="paid")

        result = webhook.change_payment_status_order()

        self.assertTrue(result)
        self.assertEqual(webhook.order.payment_status, "paid")
        webhook.order.save.assert_not_called()

    def test_failed_to_failed_duplicate_webhook_is_noop(self):
        """
        Test: order sudah failed, webhook duplikat datang lagi dengan
        transaction_status yang sama-sama menghasilkan failed (misal cancel).
        Assert: tidak ada perubahan, save() tidak dipanggil lagi, return False.
        """
        payload = {"transaction_status": "cancel", "fraud_status": None}
        webhook = self._build_webhook(payload, current_status="failed")

        result = webhook.change_payment_status_order()

        self.assertFalse(result)
        self.assertEqual(webhook.old_status, "failed")
        webhook.order.save.assert_not_called()

    def test_pending_to_failed_exposes_old_status_pending(self):
        """
        Test: order pending, transaction_status deny (transisi BARU menuju
        failed, kasus yang HARUS memicu release_reservation() di view).
        Assert: old_status ter-expose sebagai "pending" (bukan paid/failed),
        supaya guard di view (old_status not in ("paid", "failed")) benar
        mengizinkan release_reservation() jalan untuk kasus ini.
        """
        payload = {"transaction_status": "deny", "fraud_status": None}
        webhook = self._build_webhook(payload, current_status="pending")

        webhook.change_payment_status_order()

        self.assertEqual(webhook.old_status, "pending")

    def test_unrecognized_transaction_status_does_not_change_status(self):
        """
        Test: transaction_status "pending" (belum final) atau nilai lain yang
        tidak masuk kategori settlement/capture/deny/cancel/expire.
        Assert: payment_status TIDAK berubah dari status lama, save() tidak
        dipanggil, return sesuai apakah status lama == paid.
        """
        payload = {"transaction_status": "pending", "fraud_status": None}
        webhook = self._build_webhook(payload, current_status="pending")

        result = webhook.change_payment_status_order()

        self.assertFalse(result)
        self.assertEqual(webhook.order.payment_status, "pending")
        webhook.order.save.assert_not_called()


# =====================================================================
# reduce_stock
# =====================================================================
class ReduceStockTests(TestCase):

    @patch("order.services.midtrans.reduce_product_stock")
    def test_reduce_stock_runs_when_not_yet_reduced(self, mock_reduce):
        """
        Test: order.reduced_stock masih False (belum pernah dikurangi).
        Assert: reduce_product_stock terpanggil dengan items order, reduced_stock
        di-set True dan disimpan.
        """
        webhook = WebhookMidtrans()
        webhook.order = MagicMock()
        webhook.order.reduced_stock = False
        items = MagicMock()
        webhook.order.items.all.return_value = items

        webhook.reduce_stock()

        mock_reduce.assert_called_once_with(items)
        self.assertTrue(webhook.order.reduced_stock)
        webhook.order.save.assert_called_once_with(update_fields=["reduced_stock"])

    @patch("order.services.midtrans.reduce_product_stock")
    def test_reduce_stock_skipped_when_already_reduced(self, mock_reduce):
        """
        Test: order.reduced_stock sudah True (webhook duplikat/retry setelah
        sukses sebelumnya).
        Assert: reduce_product_stock TIDAK terpanggil (idempotent guard),
        save() tidak terpanggil lagi.
        """
        webhook = WebhookMidtrans()
        webhook.order = MagicMock()
        webhook.order.reduced_stock = True

        webhook.reduce_stock()

        mock_reduce.assert_not_called()
        webhook.order.save.assert_not_called()

    @patch("order.services.midtrans.logger_error")
    @patch("order.services.midtrans.reduce_product_stock")
    def test_reduce_stock_propagates_exception(self, mock_reduce, mock_logger_error):
        """
        Test: reduce_product_stock raise exception (misal stok tidak cukup,
        atau koneksi DB terputus).
        Assert: exception ter-propagate ke pemanggil (tidak ditelan), sehingga
        view dapat menangani dan membalas 500 ke Midtrans untuk retry. Logger
        exception terpanggil satu kali sebelum re-raise.
        """
        webhook = WebhookMidtrans()
        webhook.order = MagicMock()
        webhook.order.reduced_stock = False
        mock_reduce.side_effect = ValueError("Stok tidak mencukupi")

        with self.assertRaises(ValueError):
            webhook.reduce_stock()

        mock_logger_error.exception.assert_called_once()


# =====================================================================
# reverse_stock
# =====================================================================
class ReverseStockTests(TestCase):

    @patch("order.services.midtrans.restore_product_stock")
    def test_reverse_stock_skipped_when_not_reduced(self, mock_restore):
        """
        Test: order.reduced_stock False -- tidak ada stok yang pernah dikurangi
        untuk order ini (misal pending -> failed langsung, bukan reversal).
        Assert: restore_product_stock TIDAK terpanggil, tidak ada perubahan.
        """
        webhook = WebhookMidtrans()
        webhook.order = MagicMock()
        webhook.order.reduced_stock = False

        webhook.reverse_stock()

        mock_restore.assert_not_called()

    @patch("order.services.midtrans.logger")
    @patch("order.services.midtrans.restore_product_stock")
    def test_reverse_stock_restores_when_reduced_and_not_shipped(
        self, mock_restore, mock_logger
    ):
        """
        Test: order.reduced_stock True, order.status masih PENDING/PROCESSING
        (belum dikirim) -- kasus reversal normal (paid -> failed).
        Assert: restore_product_stock terpanggil dengan items order,
        reduced_stock di-set False dan disimpan.
        """
        webhook = WebhookMidtrans()
        webhook.order = MagicMock()
        webhook.order.reduced_stock = True
        webhook.order.status = "processing"
        items = MagicMock()
        webhook.order.items.all.return_value = items

        webhook.reverse_stock()

        mock_restore.assert_called_once_with(items)
        self.assertFalse(webhook.order.reduced_stock)
        webhook.order.save.assert_called_once_with(update_fields=["reduced_stock"])
        mock_logger.warning.assert_called_once()

    @patch("order.services.midtrans.logger_error")
    @patch("order.services.midtrans.restore_product_stock")
    def test_reverse_stock_skipped_when_already_shipped(
        self, mock_restore, mock_logger_error
    ):
        """
        Test: order.reduced_stock True, tapi order.status sudah SHIPPED --
        barang sudah keluar gudang, auto-restock berbahaya.
        Assert: restore_product_stock TIDAK terpanggil, reduced_stock TETAP
        True (tidak diubah), critical log terpanggil untuk manual review.
        """
        webhook = WebhookMidtrans()
        webhook.order = MagicMock()
        webhook.order.reduced_stock = True
        webhook.order.status = "shipped"

        webhook.reverse_stock()

        mock_restore.assert_not_called()
        self.assertTrue(webhook.order.reduced_stock)
        webhook.order.save.assert_not_called()
        mock_logger_error.critical.assert_called_once()

    @patch("order.services.midtrans.logger_error")
    @patch("order.services.midtrans.restore_product_stock")
    def test_reverse_stock_skipped_when_already_delivered(
        self, mock_restore, mock_logger_error
    ):
        """
        Test: order.reduced_stock True, order.status DELIVERED -- sama seperti
        shipped, barang sudah sampai ke customer.
        Assert: restore_product_stock TIDAK terpanggil, critical log terpanggil.
        """
        webhook = WebhookMidtrans()
        webhook.order = MagicMock()
        webhook.order.reduced_stock = True
        webhook.order.status = "delivered"

        webhook.reverse_stock()

        mock_restore.assert_not_called()
        mock_logger_error.critical.assert_called_once()

    @patch("order.services.midtrans.logger_error")
    @patch("order.services.midtrans.restore_product_stock")
    def test_reverse_stock_propagates_exception(self, mock_restore, mock_logger_error):
        """
        Test: restore_product_stock raise exception (misal koneksi DB terputus
        saat proses restore).
        Assert: exception ter-propagate ke pemanggil, tidak ditelan diam-diam,
        supaya view bisa log critical dan balas 500 untuk retry. Logger
        exception terpanggil satu kali sebelum re-raise.
        """
        webhook = WebhookMidtrans()
        webhook.order = MagicMock()
        webhook.order.reduced_stock = True
        webhook.order.status = "processing"
        mock_restore.side_effect = Exception("DB connection lost")

        with self.assertRaises(Exception):
            webhook.reverse_stock()

        mock_logger_error.exception.assert_called_once()


# =====================================================================
# release_reservation
# =====================================================================
class ReleaseReservationTests(TestCase):
    """
    release_reservation() sekarang TANPA guard internal -- pemicu (old_status
    not in ("paid", "failed")) dijamin benar oleh view, bukan oleh method ini.
    Jadi unit test ini murni menguji: method mengurangi reserved_stock tiap
    item sesuai qty dan memanggil save() dengan update_fields yang benar --
    TIDAK menguji kondisi kapan method ini seharusnya dipanggil (itu bagian
    dari test integration/e2e view, bukan tanggung jawab method ini lagi).
    """

    def test_release_reservation_decrements_each_item(self):
        """
        Test: order dengan beberapa item, tiap item py product dengan
        reserved_stock tertentu.
        Assert: reserved_stock tiap product berkurang sesuai qty item
        masing-masing, save() terpanggil dengan update_fields=["reserved_stock"]
        untuk tiap product.
        """
        webhook = WebhookMidtrans()
        webhook.order = MagicMock()

        item_a = MagicMock()
        item_a.qty = 2
        product_a = MagicMock()
        product_a.reserved_stock = 5
        item_a.product = product_a

        item_b = MagicMock()
        item_b.qty = 3
        product_b = MagicMock()
        product_b.reserved_stock = 4
        item_b.product = product_b

        webhook.order.items.all.return_value = [item_a, item_b]
        webhook.order.reduced_stock = False

        webhook.release_reservation()

        self.assertEqual(product_a.reserved_stock, 3)  # 5 - 2
        self.assertEqual(product_b.reserved_stock, 1)  # 4 - 3
        product_a.save.assert_called_once_with(update_fields=["reserved_stock"])
        product_b.save.assert_called_once_with(update_fields=["reserved_stock"])

    def test_release_reservation_does_not_touch_stock_field(self):
        """
        Test: release_reservation() hanya boleh menyentuh reserved_stock,
        TIDAK boleh mengubah field stock (itu tanggung jawab reduce_stock/
        reverse_stock, bukan method ini -- karena stock fisik belum pernah
        dikurangi untuk kasus pending->failed).
        Assert: product.stock tidak berubah dari nilai awal.
        """
        webhook = WebhookMidtrans()
        webhook.order = MagicMock()

        item = MagicMock()
        item.qty = 2
        product = MagicMock()
        product.reserved_stock = 5
        product.stock = 10
        item.product = product

        webhook.order.items.all.return_value = [item]
        webhook.order.reduced_stock = False

        webhook.release_reservation()

        self.assertEqual(product.stock, 10)  # tidak berubah
        self.assertEqual(product.reserved_stock, 3)  # 5 - 2

    def test_release_reservation_does_not_update_reserved_stock(self):
        """
        Test: field order.reduced_stock=True membuat release_reservation() tidak mengubah reserved_stock dan langsung return
        Assert: product.reserved_stock tidak berubah dari nilai awal.
        """
        webhook = WebhookMidtrans()
        webhook.order = MagicMock()

        item = MagicMock()
        item.qty = 2
        product = MagicMock()
        product.reserved_stock = 5
        product.stock = 10
        item.product = product

        webhook.order.items.all.return_value = [item]
        webhook.order.reduced_stock = True

        webhook.release_reservation()

        self.assertEqual(product.reserved_stock, 5)  # tidak berubah


# =====================================================================
# validate_signature
# =====================================================================
class ValidateSignatureTests(TestCase):

    def _make_payload_bytes(self, order_id, status_code, gross_amount, server_key=None):
        key = server_key if server_key is not None else settings.MIDTRANS_SERVER_KEY
        raw = f"{order_id}{status_code}{gross_amount}{key}"
        signature = hashlib.sha512(raw.encode()).hexdigest()
        payload = {
            "order_id": order_id,
            "status_code": status_code,
            "gross_amount": gross_amount,
            "signature_key": signature,
            "transaction_status": "settlement",
        }
        return json.dumps(payload).encode()

    def test_valid_payload_and_signature_returns_payload(self):
        """
        Test: payload JSON valid, signature dihitung dengan benar menggunakan
        MIDTRANS_SERVER_KEY yang sama seperti settings.
        Assert: return dict payload yang sudah di-parse, tidak raise apapun.
        """
        payload_bytes = self._make_payload_bytes("ORDER-1", "200", "100000")
        webhook = WebhookMidtrans()

        result = webhook.validate_signature(payload_bytes)

        self.assertEqual(result["order_id"], "ORDER-1")

    def test_invalid_json_raises_invalid_payload(self):
        """
        Test: body request bukan JSON valid (corrupt/kosong).
        Assert: raise InvalidMidtransPayload.
        """
        webhook = WebhookMidtrans()

        with self.assertRaises(InvalidMidtransPayload):
            webhook.validate_signature(b"not-a-json{{{")

    def test_missing_order_id_still_fails_signature_check(self):
        """
        Test: payload JSON valid tapi field order_id tidak dikirim sama sekali.
        str(None) == "None" ikut dihash, tapi signature asli (dihitung
        pengirim yang valid dari order_id sungguhan) tidak akan pernah cocok
        dengan hash yang menyertakan "None". Ini membuktikan field hilang
        TIDAK membuka celah bypass signature check.
        Assert: raise InvalidMidtransSignature, bukan lolos.
        """
        # Signature dihitung seolah-olah order_id ADA (menyimulasikan payload
        # asli yang sah), tapi payload yang divalidasi tidak menyertakan
        # order_id -- signature jadi otomatis tidak cocok.
        raw = f"ORDER-1200100000{settings.MIDTRANS_SERVER_KEY}"
        signature = hashlib.sha512(raw.encode()).hexdigest()
        payload = {
            "status_code": "200",
            "gross_amount": "100000",
            "signature_key": signature,
            "transaction_status": "settlement",
            # order_id sengaja tidak disertakan
        }
        payload_bytes = json.dumps(payload).encode()
        webhook = WebhookMidtrans()

        with self.assertRaises(InvalidMidtransSignature):
            webhook.validate_signature(payload_bytes)

    def test_mismatched_signature_raises_invalid_signature(self):
        """
        Test: payload JSON valid, tapi signature_key tidak cocok dengan hasil
        hash yang diharapkan (misal signature dipalsukan atau server_key beda).
        Assert: raise InvalidMidtransSignature.
        """
        payload_bytes = self._make_payload_bytes(
            "ORDER-1", "200", "100000", server_key="wrong-key-entirely"
        )
        webhook = WebhookMidtrans()

        with self.assertRaises(InvalidMidtransSignature):
            webhook.validate_signature(payload_bytes)
