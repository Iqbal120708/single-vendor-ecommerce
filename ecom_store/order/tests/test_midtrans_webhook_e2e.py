import hashlib
import json
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.test import TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from order.models import Order, OrderItem
from product.models import Category, Product
from rest_framework.test import APIClient

from .helper_setup import (
    set_address,
    set_location_fields,
    set_store,
    set_store_shipping_option,
    set_user,
)


class MidtransWebhookEndToEndTest(TransactionTestCase):
    """
    End-to-end test untuk MidtransWebhookView.

    Berbeda dari unit test (test_midtrans_webhook.py) dan integration test
    view dengan mock (test_midtrans_webhook_view.py) yang menguji logic dan
    wiring secara terisolasi, test ini menjalankan view asli, WebhookMidtrans
    asli, dan database asli (TransactionTestCase). Tujuannya membuktikan tiga
    hal yang tidak bisa dibuktikan lewat mock: struktur model (field, relasi
    FK) benar-benar nyambung, transaction.atomic() di view berperilaku benar
    terhadap data nyata, dan rollback lintas-blok atomic bekerja sesuai
    desain saat terjadi kegagalan di tengah proses.

    Referensi struktur kode yang diasumsikan berlaku (untuk konteks
    pembacaan test, bukan bagian dari test itu sendiri):

        WebhookMidtrans.change_payment_status_order()
            - meng-expose self.old_status dan self.new_status setelah
              diproses, dipakai view untuk menentukan kapan
              release_reservation() perlu dipanggil.

        WebhookMidtrans.release_reservation()
            - guard "if self.order.reduced_stock: return" di dalam method
              sebagai lapis pertahanan kedua; pemicu utama tetap ditentukan
              di view.

        MidtransWebhookView.post(), cabang else (is_paid False):
            - reverse_stock() selalu dipanggil (guard reduced_stock internal
              menentukan apakah benar-benar restore atau no-op).
            - release_reservation() hanya dipanggil kalau new_status
              "failed" DAN old_status bukan "paid"/"failed" -- yaitu
              transisi baru menuju failed (mis. dari pending), bukan
              reversal (old_status paid) dan bukan webhook duplikat untuk
              order yang sudah failed sebelumnya.

    Catatan desain: guard ganda (old_status DAN new_status) diperlukan
    karena old_status saja tidak cukup -- webhook dengan transaction_status
    "pending" juga menghasilkan old_status "pending" (not in paid/failed)
    tanpa ada transisi status apa pun, sehingga tanpa cek new_status,
    release_reservation() bisa salah terpanggil untuk order yang belum
    benar-benar gagal.
    """

    WEBHOOK_URL = reverse("midtrans_webhook")

    def setUp(self):
        self.client = APIClient()

        self.logger_patcher = patch("order.views_order_process.logger")
        self.mock_logger = self.logger_patcher.start()
        self.addCleanup(self.logger_patcher.stop)

        self.logger_error_patcher = patch("order.views_order_process.logger_error")
        self.mock_logger_error = self.logger_error_patcher.start()
        self.addCleanup(self.logger_error_patcher.stop)

        self.service_logger_patcher = patch("order.services.midtrans.logger")
        self.mock_service_logger = self.service_logger_patcher.start()
        self.addCleanup(self.service_logger_patcher.stop)

        self.service_logger_error_patcher = patch(
            "order.services.midtrans.logger_error"
        )
        self.mock_service_logger_error = self.service_logger_error_patcher.start()
        self.addCleanup(self.service_logger_error_patcher.stop)

        self.location_fields = set_location_fields()
        self.user = set_user()
        self.shipping_address = set_address(self.user, *self.location_fields)
        self.store = set_store(*self.location_fields)
        set_store_shipping_option(self.store)

        category, _ = Category.objects.get_or_create(
            name="Default Category", defaults={"desc": "Sample category"}
        )

        self.product_a = Product.objects.create(
            variant_name=f"Varian Product A",
            name=f"Product A",
            price=10_000,
            category=category,
            stock=10,
            weight=500,
            height=2,
            width=2,
            length=5,
        )

        self.product_b = Product.objects.create(
            variant_name=f"Varian Product B",
            name=f"Product B",
            price=30_000,
            category=category,
            stock=10,
            weight=500,
            height=2,
            width=2,
            length=5,
        )

    def _reserve_stock_for_order(self, order):
        """
        Simulasikan reservasi stok yang terjadi saat checkout (sebelum
        webhook masuk) -- reserved_stock naik sesuai qty tiap item.
        Diperlukan supaya assert reduce/restore terhadap reserved_stock
        punya baseline yang realistis, bukan langsung 0.
        """
        for item in order.items.all():
            product = item.product
            product.reserved_stock += item.qty
            product.save(update_fields=["reserved_stock"])

    def _make_order(
        self, payment_status="pending", reduced_stock=False, status="pending"
    ):
        order = Order.objects.create(
            user=self.user,
            store=self.store,
            payment_status=payment_status,
            reduced_stock=reduced_stock,
            status=status,
        )
        OrderItem.objects.create(
            order=order,
            product=self.product_a,
            product_price=self.product_a.price,
            qty=2,
        )
        OrderItem.objects.create(
            order=order,
            product=self.product_b,
            product_price=self.product_b.price,
            qty=3,
        )
        return order

    def _signed_payload(
        self,
        order_id,
        transaction_status,
        fraud_status=None,
        status_code="200",
        gross_amount="190000",
    ):
        raw = f"{order_id}{status_code}{gross_amount}{settings.MIDTRANS_SERVER_KEY}"
        signature = hashlib.sha512(raw.encode()).hexdigest()
        payload = {
            "order_id": str(order_id),
            "status_code": status_code,
            "gross_amount": gross_amount,
            "signature_key": signature,
            "transaction_status": transaction_status,
        }
        if fraud_status is not None:
            payload["fraud_status"] = fraud_status
        return json.dumps(payload).encode()

    def _post(self, body):
        return self.client.post(
            self.WEBHOOK_URL, data=body, content_type="application/json"
        )

    # -----------------------------------------------------------------
    # 1. Happy path
    # -----------------------------------------------------------------
    def test_settlement_pending_order_becomes_paid_and_stock_reduced(self):
        """
        Test: order pending, webhook settlement (fraud_status None, metode
        non-kartu seperti QRIS/bank transfer).
        Assert: response 200, payment_status jadi paid, stok kedua produk
        berkurang sesuai qty, reduced_stock jadi True.
        """
        order = self._make_order(payment_status="pending")
        self._reserve_stock_for_order(order)
        body = self._signed_payload(order.order_id, "settlement", fraud_status=None)

        response = self._post(body)

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.product_a.refresh_from_db()
        self.product_b.refresh_from_db()
        self.assertEqual(order.payment_status, "paid")
        self.assertTrue(order.reduced_stock)
        self.assertEqual(self.product_a.stock, 8)  # 10 - 2
        self.assertEqual(self.product_b.stock, 7)  # 10 - 3
        self.assertEqual(self.product_a.reserved_stock, 0)  # 2 - 2, reservasi dilepas
        self.assertEqual(self.product_b.reserved_stock, 0)  # 3 - 3, reservasi dilepas

    # -----------------------------------------------------------------
    # 2. Payment gagal, bukan reversal
    # -----------------------------------------------------------------
    def test_deny_pending_order_becomes_failed_reservation_released(self):
        """
        Test: order pending, webhook deny (belum pernah paid, belum pernah
        reduce_stock -- reduced_stock masih False).
        Assert: response 200, payment_status jadi failed, Product.stock
        TIDAK berubah (karena reduce_stock belum pernah dipanggil), TAPI
        reserved_stock HARUS dilepas kembali ke 0 lewat release_reservation()
        -- reservasi checkout yang gagal bayar tidak boleh menggantung
        selamanya di reserved_stock, karena itu membuat stok kelihatan
        habis padahal barang fisik masih ada.
        """
        order = self._make_order(payment_status="pending")
        self._reserve_stock_for_order(order)
        body = self._signed_payload(order.order_id, "deny")

        response = self._post(body)

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.product_a.refresh_from_db()
        self.product_b.refresh_from_db()
        self.assertEqual(order.payment_status, "failed")
        self.assertFalse(order.reduced_stock)
        self.assertEqual(self.product_a.stock, 10)  # stok fisik tidak berubah
        self.assertEqual(self.product_b.stock, 10)
        self.assertEqual(self.product_a.reserved_stock, 0)  # dilepas
        self.assertEqual(self.product_b.reserved_stock, 0)  # dilepas

    # -----------------------------------------------------------------
    # 3. Reversal
    # -----------------------------------------------------------------
    def test_reversal_does_not_double_release_reservation(self):
        """
        Test: order paid + reduced_stock True (reservasi sudah closed sejak
        dulu, reserved_stock sudah 0 sejak reduce_stock jalan), webhook deny
        datang (reversal). old_status untuk kasus ini adalah "paid", BUKAN
        "failed" -- ini kasus krusial yang membuktikan guard "old_status not
        in (paid, failed)" bekerja benar, karena kalau guard salah desain
        (misal cuma cek old_status != "failed" tanpa exclude "paid" juga),
        release_reservation() akan salah kena panggil di sini dan membuat
        reserved_stock jadi minus (karena sudah 0, dikurangi lagi).
        Assert: response 200, reserved_stock TETAP 0 (bukan minus).
        """
        order = self._make_order(payment_status="paid", reduced_stock=True)
        self._reserve_stock_for_order(order)
        # Simulasikan kondisi setelah reduce_stock sukses sebelumnya:
        # reserved_stock sudah dilepas ke 0, stock sudah dikurangi
        self.product_a.stock = 8
        self.product_a.reserved_stock = 0
        self.product_a.save(update_fields=["stock", "reserved_stock"])
        self.product_b.stock = 7
        self.product_b.reserved_stock = 0
        self.product_b.save(update_fields=["stock", "reserved_stock"])

        body = self._signed_payload(order.order_id, "deny")

        response = self._post(body)

        self.assertEqual(response.status_code, 200)
        self.product_a.refresh_from_db()
        self.product_b.refresh_from_db()
        self.assertEqual(self.product_a.reserved_stock, 0)  # bukan -2
        self.assertEqual(self.product_b.reserved_stock, 0)  # bukan -3

    def test_release_reservation_skipped_when_already_reduced_stock(self):
        """
        Test: order sudah paid + reduced_stock True, webhook deny datang
        (reversal, bukan pending->failed). release_reservation() harus
        SKIP karena reduced_stock True berarti reservasi sudah "closed"
        duluan oleh reduce_stock() -- reserved_stock jangan disentuh lagi
        di jalur reversal (itu tanggung jawab reverse_stock, yang memang
        tidak menyentuh reserved_stock sama sekali).
        """
        order = self._make_order(payment_status="paid", reduced_stock=True)
        self._reserve_stock_for_order(order)
        # Simulasikan kondisi setelah reduce_stock sukses: reserved_stock
        # sudah 0, stock sudah dikurangi
        self.product_a.stock = 8
        self.product_a.reserved_stock = 0
        self.product_a.save(update_fields=["stock", "reserved_stock"])
        self.product_b.stock = 7
        self.product_b.reserved_stock = 0
        self.product_b.save(update_fields=["stock", "reserved_stock"])

        body = self._signed_payload(order.order_id, "deny")

        response = self._post(body)

        self.assertEqual(response.status_code, 200)
        self.product_a.refresh_from_db()
        self.product_b.refresh_from_db()
        # tetap 0, tidak jadi minus karena release_reservation salah kena
        self.assertEqual(self.product_a.reserved_stock, 0)
        self.assertEqual(self.product_b.reserved_stock, 0)

    def test_duplicate_deny_webhook_does_not_double_release_reservation(self):
        """
        Test: order sudah failed (reserved_stock sudah dilepas oleh webhook
        deny pertama), webhook deny duplikat datang lagi.
        Assert: reserved_stock TIDAK berkurang lagi jadi minus -- perlu
        guard idempotency di release_reservation() sendiri, serupa pola
        reduced_stock, supaya tidak double-decrement.
        """
        order = self._make_order(payment_status="failed", reduced_stock=False)
        # reserved_stock sudah 0 (sudah dilepas oleh webhook pertama)
        body = self._signed_payload(order.order_id, "deny")

        response = self._post(body)

        self.assertEqual(response.status_code, 200)
        self.product_a.refresh_from_db()
        self.product_b.refresh_from_db()
        self.assertEqual(self.product_a.reserved_stock, 0)  # tidak jadi -2
        self.assertEqual(self.product_b.reserved_stock, 0)  # tidak jadi -3

    def test_reversal_paid_to_failed_restores_stock(self):
        """
        Test: order sudah paid dan reduced_stock True (stok sudah dikurangi
        sebelumnya), webhook deny datang (reversal, kasus nyata Permata/
        Mandiri Bill Payment/Indomaret).
        Assert: response 200, payment_status jadi failed, stok kedua produk
        BERTAMBAH kembali sesuai qty, reduced_stock jadi False.
        """
        order = self._make_order(payment_status="paid", reduced_stock=True)
        self._reserve_stock_for_order(order)
        # Simulasikan stok yang sudah dikurangi sebelumnya (reduce_stock
        # sudah jalan duluan, artinya reserved_stock sudah dilepas jadi 0)
        self.product_a.stock = 8
        self.product_a.reserved_stock = 0
        self.product_a.save(update_fields=["stock", "reserved_stock"])
        self.product_b.stock = 7
        self.product_b.reserved_stock = 0
        self.product_b.save(update_fields=["stock", "reserved_stock"])

        body = self._signed_payload(order.order_id, "deny")

        response = self._post(body)

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.product_a.refresh_from_db()
        self.product_b.refresh_from_db()
        self.assertEqual(order.payment_status, "failed")
        self.assertFalse(order.reduced_stock)
        self.assertEqual(self.product_a.stock, 10)
        self.assertEqual(self.product_b.stock, 10)
        # restore_product_stock TIDAK menyentuh reserved_stock -- reservasi
        # sudah closed sejak reduce_stock jalan, tetap 0 setelah restore
        self.assertEqual(self.product_a.reserved_stock, 0)
        self.assertEqual(self.product_b.reserved_stock, 0)

    def test_reversal_skipped_when_order_already_shipped(self):
        """
        Test: order paid + reduced_stock True, TAPI status sudah SHIPPED.
        Assert: response 200, payment_status jadi failed, stok TIDAK
        bertambah (skip restore, karena barang sudah keluar gudang).
        """
        order = self._make_order(
            payment_status="paid", reduced_stock=True, status="shipped"
        )
        self.product_a.stock = 8
        self.product_a.save(update_fields=["stock"])
        self.product_b.stock = 7
        self.product_b.save(update_fields=["stock"])

        body = self._signed_payload(order.order_id, "deny")

        response = self._post(body)

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.product_a.refresh_from_db()
        self.product_b.refresh_from_db()
        self.assertEqual(order.payment_status, "failed")
        self.assertTrue(order.reduced_stock)  # tidak diubah, karena skip
        self.assertEqual(self.product_a.stock, 8)  # tidak bertambah
        self.assertEqual(self.product_b.stock, 7)

    # -----------------------------------------------------------------
    # 4. Idempotency
    # -----------------------------------------------------------------
    def test_duplicate_settlement_webhook_does_not_reduce_stock_again(self):
        """
        Test: order sudah paid + reduced_stock True, webhook settlement
        datang lagi (duplikat/retry Midtrans).
        Assert: response 200, stok TIDAK berkurang lagi (masih sama seperti
        setelah pengurangan pertama).
        """
        order = self._make_order(payment_status="paid", reduced_stock=True)
        self.product_a.stock = 8
        self.product_a.save(update_fields=["stock"])
        self.product_b.stock = 7
        self.product_b.save(update_fields=["stock"])

        body = self._signed_payload(order.order_id, "settlement", fraud_status=None)

        response = self._post(body)

        self.assertEqual(response.status_code, 200)
        self.product_a.refresh_from_db()
        self.product_b.refresh_from_db()
        self.assertEqual(self.product_a.stock, 8)
        self.assertEqual(self.product_b.stock, 7)

    def test_settlement_after_already_failed_is_blocked(self):
        """
        Test: order sudah failed (dari deny/cancel sebelumnya), webhook
        settlement datang telat/retry.
        Assert: response 200, payment_status TETAP failed (transisi
        failed->paid diblokir), stok tidak berubah.
        """
        order = self._make_order(payment_status="failed", reduced_stock=False)
        body = self._signed_payload(order.order_id, "settlement", fraud_status="accept")

        response = self._post(body)

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.product_a.refresh_from_db()
        self.assertEqual(order.payment_status, "failed")
        self.assertFalse(order.reduced_stock)
        self.assertEqual(self.product_a.stock, 10)

    # -----------------------------------------------------------------
    # 5. Validasi gagal (sebelum sentuh DB)
    # -----------------------------------------------------------------
    def test_invalid_signature_returns_403_no_db_change(self):
        """
        Test: signature_key tidak cocok.
        Assert: response 403, order TIDAK berubah sama sekali.
        """
        order = self._make_order(payment_status="pending")
        raw = f"{order.order_id}200190000wrong-key"
        bad_signature = hashlib.sha512(raw.encode()).hexdigest()
        payload = {
            "order_id": str(order.order_id),
            "status_code": "200",
            "gross_amount": "190000",
            "signature_key": bad_signature,
            "transaction_status": "settlement",
        }
        body = json.dumps(payload).encode()

        response = self._post(body)

        self.assertEqual(response.status_code, 403)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "pending")

    def test_order_not_found_returns_404(self):
        """
        Test: order_id valid formatnya tapi tidak ada row yang cocok di DB.
        Assert: response 404.
        """
        body = self._signed_payload(
            "ORDER-DOES-NOT-EXIST", "settlement", fraud_status=None
        )

        response = self._post(body)

        self.assertEqual(response.status_code, 404)

    # -----------------------------------------------------------------
    # 6. Rollback -- reduce_stock gagal di tengah loop (item ke-2)
    # -----------------------------------------------------------------
    def test_reduce_stock_failure_rolls_back_earlier_item_in_same_loop(self):
        """
        Test: order dengan 2 item. Product A stok cukup (akan diproses
        duluan dalam loop), Product B stok TIDAK cukup (qty diminta 3,
        stok cuma 1) -- memicu ValueError alami di iterasi kedua.
        Assert: response 500, payment_status TETAP paid (blok atomic
        reduce_stock terpisah dari blok status, sudah commit duluan),
        TAPI stok Product A yang sudah ke-save() di iterasi pertama
        HARUS ikut rollback -- masih 10, tidak ikut berkurang jadi 8.
        Ini membuktikan transaction.atomic() di view membungkus seluruh
        loop sebagai satu unit, bukan per-item.
        """
        self.product_b.stock = 1  # kurang dari qty (3) yang diminta OrderItem
        self.product_b.save(update_fields=["stock"])

        order = self._make_order(payment_status="pending")
        body = self._signed_payload(order.order_id, "settlement", fraud_status=None)

        response = self._post(body)

        self.assertEqual(response.status_code, 500)
        order.refresh_from_db()
        self.product_a.refresh_from_db()
        self.product_b.refresh_from_db()
        self.assertEqual(order.payment_status, "paid")  # blok pertama tetap commit
        self.assertFalse(order.reduced_stock)  # gagal, jadi tetap False
        self.assertEqual(self.product_a.stock, 10)  # ROLLBACK, bukan 8
        self.assertEqual(self.product_b.stock, 1)  # tidak berubah, gagal duluan

    # -----------------------------------------------------------------
    # 7. Rollback -- restore_product_stock sukses penuh, tapi Order.save gagal
    # -----------------------------------------------------------------
    def test_reverse_stock_order_save_failure_rolls_back_restored_stock(self):
        """
        Test: order paid + reduced_stock True, webhook deny (reversal).
        restore_product_stock() berhasil PENUH -- semua item stoknya
        sudah bertambah kembali di level Python/DB write. Tapi
        self.order.save(update_fields=["reduced_stock"]) yang dipanggil
        SETELAHNYA dipaksa gagal (misal DB connection putus di titik itu).
        Assert: response 500, DAN karena restore_product_stock dan
        self.order.save() berada di satu blok atomic yang sama (blok
        kedua di view), kegagalan save() harus me-rollback SEMUA
        perubahan stock yang sudah terjadi -- Product A dan B harus
        KEMBALI ke nilai sebelum restore (8 dan 7), bukan ikut naik
        jadi 10. payment_status tetap failed (blok pertama independen,
        sudah commit duluan).
        """
        order = self._make_order(payment_status="paid", reduced_stock=True)
        self.product_a.stock = 8
        self.product_a.save(update_fields=["stock"])
        self.product_b.stock = 7
        self.product_b.save(update_fields=["stock"])

        body = self._signed_payload(order.order_id, "deny")

        # Aktifkan mock HANYA untuk request webhook -- setup data di atas
        # (create order, product) sudah selesai duluan, jadi hitungan
        # panggilan save() di sini murni yang terjadi di dalam
        # MidtransWebhookView.post(): save #1 = payment_status (blok
        # pertama, harus tetap sukses), save #2 = reduced_stock (blok
        # kedua, dipaksa gagal).
        call_count = {"n": 0}
        original_save = Order.save

        def save_side_effect(self_order, *args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return original_save(self_order, *args, **kwargs)
            raise Exception("DB connection lost saat save order")

        with patch.object(Order, "save", autospec=True, side_effect=save_side_effect):
            response = self._post(body)

        self.assertEqual(response.status_code, 500)
        order.refresh_from_db()
        self.product_a.refresh_from_db()
        self.product_b.refresh_from_db()
        self.assertEqual(order.payment_status, "failed")  # blok pertama tetap commit
        self.assertTrue(order.reduced_stock)  # save gagal, field ini tidak ter-update
        self.assertEqual(self.product_a.stock, 8)  # ROLLBACK, bukan 10
        self.assertEqual(self.product_b.stock, 7)  # ROLLBACK, bukan 10

    # -----------------------------------------------------------------
    # 8. Rollback -- blok pertama gagal total (mock paksa)
    # -----------------------------------------------------------------
    def test_change_payment_status_failure_rolls_back_completely(self):
        """
        Test: change_payment_status_order() dipaksa gagal (Order.save
        di-mock raise exception) saat proses ubah status.
        Assert: response 500, payment_status di DB TETAP seperti semula
        (pending) -- bukti blok atomic pertama (get_order +
        change_payment_status_order) rollback penuh saat gagal di tengah.
        """
        order = self._make_order(payment_status="pending")
        body = self._signed_payload(order.order_id, "settlement", fraud_status=None)

        # Mock diaktifkan HANYA saat request webhook diproses -- setup data
        # di atas (_make_order, yang juga memanggil Order.save() secara
        # internal lewat objects.create()) sudah selesai duluan, supaya
        # tidak ikut kena side_effect.
        with patch.object(
            Order, "save", side_effect=Exception("DB error saat save status")
        ):
            response = self._post(body)

        self.assertEqual(response.status_code, 500)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "pending")  # tidak berubah sama sekali
