from unittest.mock import patch

from django.urls import reverse
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from rest_framework.test import APITestCase
from rest_framework import status
from datetime import timedelta
from order.models import Order, OrderItem, OrderShipping
from product.models import Product, Category
from order.services.refund import RefundService
from order.models import RefundRequest

from .helper_setup import set_location_fields, set_user, set_store, set_store_shipping_option


class RefundTestBase(TestCase):
    def setUp(self):
        self.province, self.city, self.district = set_location_fields()
        self.store = set_store(self.province, self.city, self.district)
        set_store_shipping_option(self.store)
        self.user = set_user(username="customer1", email="customer1@test.com")

        category = Category.objects.create(name="Kategori Test")
        self.product = Product.objects.create(
            variant_name="Varian Product A",
            name="Product A",
            price=25000,
            category=category,
            stock=10,
            reserved_stock=2,
            weight=500,
            height=2,
            width=2,
            length=5,
        )

        self.order = self._create_order(order_status=Order.Status.DELIVERED)
        self.order.reduced_stock = True
        self.order.save(update_fields=["reduced_stock"])

        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_price=self.product.price,
            qty=1,
        )

        self.refund_request = RefundRequest.objects.create(
            order_item=self.order_item,
            amount=self.order_item.subtotal,
            reason=RefundRequest.Reason.RETURN,
            destination_type=RefundRequest.DestinationType.BANK,
            destination_provider=RefundRequest.Provider.BCA,
            destination_number="1234567890",
            account_holder_name="Customer Satu",
        )

    def _create_order(self, order_status=Order.Status.PENDING, with_shipping=True):
        order = Order.objects.create(
            user=self.user,
            store=self.store,
            status=order_status,
            payment_status=Order.PaymentStatus.PAID,
        )

        if with_shipping:
            OrderShipping.objects.create(
                order=order,
                shipping_name="JNE",
                service_name="REG",
                etd="2-3",
                shipping_cost=10000,
                shipping_cost_net=10000,
                service_fee=1000,
                origin_ro=1,
                origin_address="Jakarta",
                destination_ro=2,
                destination_address="Cirebon",
            )

        return order


# =====================================================================
# 1. approve()
# =====================================================================
class RefundServiceApproveTests(RefundTestBase):

    @patch("order.services.refund.send_refund_status_email")
    def test_approve_success_from_requested(self, mock_email):
        """
        Test: approve() dipanggil pada RefundRequest berstatus REQUESTED.
        Assert: status jadi APPROVED, approved_at terisi, email terkirim.
        """
        RefundService(self.refund_request).approve()
        self.refund_request.refresh_from_db()

        self.assertEqual(self.refund_request.status, RefundRequest.Status.APPROVED)
        self.assertIsNotNone(self.refund_request.approved_at)
        mock_email.delay.assert_called_once_with(self.refund_request.id)

    @patch("order.services.refund.send_refund_status_email")
    def test_approve_fails_when_status_not_requested(self, mock_email):
        """
        Test: approve() dipanggil pada RefundRequest yang sudah APPROVED.
        Assert: raise ValidationError, email tidak terkirim.
        """
        self.refund_request.status = RefundRequest.Status.APPROVED
        self.refund_request.save(update_fields=["status"])

        with self.assertRaises(ValidationError):
            RefundService(self.refund_request).approve()

        mock_email.delay.assert_not_called()


# =====================================================================
# 2. reject()
# =====================================================================
class RefundServiceRejectTests(RefundTestBase):

    @patch("order.services.refund.send_refund_status_email")
    def test_reject_success_from_requested(self, mock_email):
        """
        Test: reject() dipanggil pada RefundRequest berstatus REQUESTED.
        Assert: status jadi REJECTED, approved_at terisi, email terkirim.
        """
        RefundService(self.refund_request).reject()
        self.refund_request.refresh_from_db()

        self.assertEqual(self.refund_request.status, RefundRequest.Status.REJECTED)
        self.assertIsNotNone(self.refund_request.approved_at)
        mock_email.delay.assert_called_once_with(self.refund_request.id)

    @patch("order.services.refund.send_refund_status_email")
    def test_reject_fails_when_status_not_requested(self, mock_email):
        """
        Test: reject() dipanggil pada RefundRequest yang sudah COMPLETED.
        Assert: raise ValidationError, email tidak terkirim.
        """
        self.refund_request.status = RefundRequest.Status.COMPLETED
        self.refund_request.save(update_fields=["status"])

        with self.assertRaises(ValidationError):
            RefundService(self.refund_request).reject()

        mock_email.delay.assert_not_called()


# =====================================================================
# 3. complete()
# =====================================================================
class RefundServiceCompleteTests(RefundTestBase):

    def setUp(self):
        super().setUp()
        self.refund_request.status = RefundRequest.Status.APPROVED
        self.refund_request.save(update_fields=["status"])

    @patch("order.services.refund.send_refund_status_email")
    def test_fails_when_status_not_approved(self, mock_email):
        """
        Test: complete() dipanggil saat RefundRequest masih REQUESTED.
        Assert: raise ValidationError, status tidak berubah, email tidak terkirim.
        """
        self.refund_request.status = RefundRequest.Status.REQUESTED
        self.refund_request.save(update_fields=["status"])

        with self.assertRaises(ValidationError):
            RefundService(self.refund_request).complete()

        self.refund_request.refresh_from_db()
        self.assertEqual(self.refund_request.status, RefundRequest.Status.REQUESTED)
        mock_email.delay.assert_not_called()

    @patch("order.services.refund.send_refund_status_email")
    def test_fails_when_order_status_invalid(self, mock_email):
        """
        Test: Order.status di luar [PENDING, PROCESSING, SHIPPED, DELIVERED].
        Catatan: karena Order.Status enum sekarang HANYA berisi 4 nilai itu
        (CANCELED sudah dihapus), kondisi ini tidak bisa dicapai lewat cara
        normal -- disimulasikan lewat .update() langsung ke DB untuk menguji
        guard tetap berfungsi kalau ada data legacy/korup dengan nilai lain.
        Assert: raise ValidationError, RefundRequest tetap APPROVED, email tidak terkirim.
        """
        Order.objects.filter(pk=self.order.pk).update(status="unknown_status")

        with self.assertRaises(ValidationError):
            RefundService(self.refund_request).complete()

        self.refund_request.refresh_from_db()
        self.assertEqual(self.refund_request.status, RefundRequest.Status.APPROVED)
        mock_email.delay.assert_not_called()

    @patch("order.services.refund.send_refund_status_email")
    def test_fails_when_payment_failed(self, mock_email):
        """
        Test: Order.payment_status FAILED (pembayaran gagal/reversal).
        Assert: raise ValidationError, mencegah double-adjust stock, email tidak terkirim.
        """
        self.order.payment_status = Order.PaymentStatus.FAILED
        self.order.save(update_fields=["payment_status"])

        with self.assertRaises(ValidationError):
            RefundService(self.refund_request).complete()

        self.refund_request.refresh_from_db()
        self.assertEqual(self.refund_request.status, RefundRequest.Status.APPROVED)
        mock_email.delay.assert_not_called()

    @patch("order.services.refund.send_refund_anomaly_email")
    @patch("order.services.refund.logger_error")
    @patch("order.services.refund.send_refund_status_email")
    def test_fails_when_paid_but_not_reduced_stock_anomaly(
        self, mock_status_email, mock_logger_error, mock_anomaly_email
    ):
        """
        Test: payment_status PAID tapi reduced_stock False (reduce_stock webhook gagal).
        Assert: raise ValidationError, log critical + email anomali terkirim ke store,
        email status ke customer TIDAK terkirim (beda tujuan/tujuan gagal).
        """
        self.order.payment_status = Order.PaymentStatus.PAID
        self.order.reduced_stock = False
        self.order.save(update_fields=["payment_status", "reduced_stock"])
    
        with self.assertRaises(ValidationError):
            RefundService(self.refund_request).complete()
    
        self.refund_request.refresh_from_db()
        self.assertEqual(self.refund_request.status, RefundRequest.Status.APPROVED)
    
        mock_logger_error.critical.assert_called_once()
        mock_anomaly_email.delay.assert_called_once_with(self.order.id, self.refund_request.id)
        mock_status_email.delay.assert_not_called()
    
    @patch("order.services.refund.send_refund_status_email")
    def test_success_restores_stock_when_reduced_stock_true(self, mock_email):
        """
        Test: happy path, stock sudah pernah dikurangi (reduced_stock=True).
        Assert: status COMPLETED, product.stock bertambah qty, reserved_stock tidak berubah.
        """
        self.order.reduced_stock = True
        self.order.payment_status = Order.PaymentStatus.PAID
        self.order.save(update_fields=["reduced_stock", "payment_status"])

        stock_before = self.product.stock
        reserved_before = self.product.reserved_stock

        RefundService(self.refund_request).complete()

        self.refund_request.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(self.refund_request.status, RefundRequest.Status.COMPLETED)
        self.assertIsNotNone(self.refund_request.completed_at)
        self.assertEqual(self.product.stock, stock_before + self.order_item.qty)
        self.assertEqual(self.product.reserved_stock, reserved_before)
        mock_email.delay.assert_called_once_with(self.refund_request.id)

    @patch("order.services.refund.send_refund_status_email")
    def test_success_releases_reserved_when_reduced_stock_false(self, mock_email):
        """
        Test: happy path, stock belum pernah dikurangi (reduced_stock=False, belum PAID).
        Assert: status COMPLETED, reserved_stock berkurang qty, product.stock tidak berubah.
        """
        self.order.reduced_stock = False
        self.order.payment_status = Order.PaymentStatus.PENDING
        self.order.status = Order.Status.PENDING
        self.order.save(update_fields=["reduced_stock", "payment_status", "status"])

        stock_before = self.product.stock
        reserved_before = self.product.reserved_stock

        RefundService(self.refund_request).complete()

        self.refund_request.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(self.refund_request.status, RefundRequest.Status.COMPLETED)
        self.assertEqual(self.product.stock, stock_before)
        self.assertEqual(self.product.reserved_stock, reserved_before - self.order_item.qty)
        mock_email.delay.assert_called_once_with(self.refund_request.id)


# =====================================================================
# 4. create (lewat RefundRequestCreateView)
# =====================================================================
class RefundRequestCreateViewTests(APITestCase):

    def setUp(self):
        self.province, self.city, self.district = set_location_fields()
        self.store = set_store(self.province, self.city, self.district)
        set_store_shipping_option(self.store)
        self.user = set_user(username="customer1", email="customer1@test.com")
        self.other_user = set_user(
            username="customer2", email="customer2@test.com", phone_number="089384442948"
        )

        category = Category.objects.create(name="Kategori Test")
        self.product = Product.objects.create(
            variant_name="Varian Product A",
            name="Product A",
            price=25000,
            category=category,
            stock=10,
            reserved_stock=2,
            weight=500,
            height=2,
            width=2,
            length=5,
        )

        self.order = self._create_order(order_status=Order.Status.PENDING)
        self.order.payment_status = Order.PaymentStatus.UNPAID
        self.order.save(update_fields=["payment_status"])

        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_price=self.product.price,
            qty=1,
        )

        self.client.force_authenticate(user=self.user)
        self.url = reverse("refund_request_create")
        self.valid_payload = {
            "order_item": self.order_item.id,
            "destination_type": RefundRequest.DestinationType.BANK,
            "destination_provider": RefundRequest.Provider.BCA,
            "destination_number": "1234567890",
            "account_holder_name": "Customer Satu",
        }

    def _create_order(self, order_status=Order.Status.PENDING, with_shipping=True):
        order = Order.objects.create(
            user=self.user,
            store=self.store,
            status=order_status,
            payment_status=Order.PaymentStatus.PAID,
        )

        if with_shipping:
            OrderShipping.objects.create(
                order=order,
                shipping_name="JNE",
                service_name="REG",
                etd="2-3",
                shipping_cost=10000,
                shipping_cost_net=10000,
                service_fee=1000,
                origin_ro=1,
                origin_address="Jakarta",
                destination_ro=2,
                destination_address="Cirebon",
            )

        return order

    @patch("order.serializers.send_refund_created_email")
    def test_create_success_sets_reason_and_amount_automatically(self, mock_email):
        """
        Test: order.status PENDING, customer ajukan refund dengan payload valid.
        Assert: 201, reason otomatis CUSTOMER_CANCEL, amount otomatis dari subtotal
        (bukan dari input customer), email created terkirim.
        """
        response = self.client.post(self.url, self.valid_payload)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        refund_request = RefundRequest.objects.get(order_item=self.order_item)
        self.assertEqual(refund_request.reason, RefundRequest.Reason.CUSTOMER_CANCEL)
        self.assertEqual(refund_request.amount, self.order_item.subtotal)
        mock_email.delay.assert_called_once_with(refund_request.id)

    @patch("order.serializers.send_refund_created_email")
    def test_create_sets_reason_return_when_order_delivered(self, mock_email):
        """
        Test: order.status DELIVERED, customer ajukan refund.
        Assert: 201, reason otomatis RETURN (bukan CUSTOMER_CANCEL).
        """
        self.order.status = Order.Status.DELIVERED
        self.order.payment_status = Order.PaymentStatus.PAID
        self.order.save(update_fields=["status", "payment_status"])

        response = self.client.post(self.url, self.valid_payload)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        refund_request = RefundRequest.objects.get(order_item=self.order_item)
        self.assertEqual(refund_request.reason, RefundRequest.Reason.RETURN)

    def test_create_fails_when_order_item_not_owned_by_user(self):
        """
        Test: order_item milik user lain, bukan user yang login (IDOR).
        Assert: 400, tidak ada RefundRequest yang terbuat.
        """
        self.client.force_authenticate(user=self.other_user)

        response = self.client.post(self.url, self.valid_payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(RefundRequest.objects.filter(order_item=self.order_item).exists())

    def test_create_fails_when_item_has_active_refund(self):
        """
        Test: order_item sudah punya RefundRequest berstatus REQUESTED.
        Assert: 400, tidak ada RefundRequest kedua yang terbuat.
        """
        RefundRequest.objects.create(
            order_item=self.order_item,
            amount=self.order_item.subtotal,
            reason=RefundRequest.Reason.CUSTOMER_CANCEL,
            destination_type=RefundRequest.DestinationType.BANK,
            destination_provider=RefundRequest.Provider.BCA,
            destination_number="1234567890",
            account_holder_name="Customer Satu",
        )

        response = self.client.post(self.url, self.valid_payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(RefundRequest.objects.filter(order_item=self.order_item).count(), 1)

    def test_create_fails_when_bank_provider_invalid_for_destination_type(self):
        """
        Test: destination_type BANK tapi destination_provider GOPAY (bukan bank).
        Assert: 400, error pada field destination_provider.
        """
        payload = {**self.valid_payload, "destination_provider": RefundRequest.Provider.GOPAY}

        response = self.client.post(self.url, payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("destination_provider", response.data)

    def test_create_fails_when_order_status_not_refundable(self):
        """
        Test: order.status di luar PENDING/PROCESSING/SHIPPED/DELIVERED
        (disimulasikan lewat .update() karena enum resmi hanya 4 nilai itu).
        Assert: 400, tidak ada RefundRequest yang terbuat.
        """
        Order.objects.filter(pk=self.order.pk).update(status="unknown_status")

        response = self.client.post(self.url, self.valid_payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(RefundRequest.objects.filter(order_item=self.order_item).exists())

    def test_create_fails_when_order_has_no_shipping(self):
        """
        Test: order belum menyelesaikan checkout (tidak ada OrderShipping).
        Assert: 400, tidak ada RefundRequest yang terbuat.
        """
        order_without_shipping = self._create_order(
            order_status=Order.Status.PENDING, with_shipping=False
        )
        order_item = OrderItem.objects.create(
            order=order_without_shipping,
            product=self.product,
            product_price=self.product.price,
            qty=1,
        )
        payload = {**self.valid_payload, "order_item": order_item.id}
    
        response = self.client.post(self.url, payload)
    
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(RefundRequest.objects.filter(order_item=order_item).exists())
        
class RefundRequestByItemViewTests(APITestCase):

    def setUp(self):
        self.province, self.city, self.district = set_location_fields()
        self.store = set_store(self.province, self.city, self.district)
        set_store_shipping_option(self.store)
        self.user = set_user(username="customer1", email="customer1@test.com")
        self.other_user = set_user(
            username="customer2", email="customer2@test.com", phone_number="089384442948"
        )

        category = Category.objects.create(name="Kategori Test")
        self.product = Product.objects.create(
            variant_name="Varian Product A",
            name="Product A",
            price=25000,
            category=category,
            stock=10,
            reserved_stock=2,
            weight=500,
            height=2,
            width=2,
            length=5,
        )

        self.order = Order.objects.create(
            user=self.user, store=self.store,
            status=Order.Status.PENDING, payment_status=Order.PaymentStatus.UNPAID,
        )
        OrderShipping.objects.create(
            order=self.order, shipping_name="JNE", service_name="REG", etd="2-3",
            shipping_cost=10000, shipping_cost_net=10000, service_fee=1000,
            origin_ro=1, origin_address="Jakarta", destination_ro=2, destination_address="Cirebon",
        )
        self.order_item = OrderItem.objects.create(
            order=self.order, product=self.product, product_price=self.product.price, qty=1,
        )

        self.client.force_authenticate(user=self.user)
        self.url = reverse("refund_request_by_item", args=[self.order_item.id])

    def test_returns_404_when_no_refund_request_exists(self):
        """
        Test: order_item belum pernah diajukan refund sama sekali.
        Assert: 404 dengan pesan jelas, bukan 200 dengan data kosong.
        """
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_returns_latest_refund_request(self):
        """
        Test: order_item punya 2 riwayat RefundRequest (1 REJECTED lama,
        1 REQUESTED baru -- kasus resubmit setelah ditolak).
        Assert: 200, data yang dikembalikan adalah yang requested_at terbaru
        (REQUESTED), bukan yang lama (REJECTED).
        """
        older = RefundRequest.objects.create(
            order_item=self.order_item,
            amount=self.order_item.subtotal,
            reason=RefundRequest.Reason.CUSTOMER_CANCEL,
            status=RefundRequest.Status.REJECTED,
            destination_type=RefundRequest.DestinationType.BANK,
            destination_provider=RefundRequest.Provider.BCA,
            destination_number="1234567890",
            account_holder_name="Customer Satu",
        )
        RefundRequest.objects.filter(pk=older.pk).update(
            requested_at=timezone.now() - timedelta(days=1)
        )

        newest = RefundRequest.objects.create(
            order_item=self.order_item,
            amount=self.order_item.subtotal,
            reason=RefundRequest.Reason.CUSTOMER_CANCEL,
            status=RefundRequest.Status.REQUESTED,
            destination_type=RefundRequest.DestinationType.BANK,
            destination_provider=RefundRequest.Provider.BCA,
            destination_number="1234567890",
            account_holder_name="Customer Satu",
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], newest.id)
        self.assertEqual(response.data["status"], RefundRequest.Status.REQUESTED)

    def test_returns_404_when_refund_request_belongs_to_other_user(self):
        """
        Test: order_item milik user lain punya RefundRequest, tapi user yang
        login mencoba akses order_item_id itu (IDOR).
        Assert: 404 (bukan 403) -- tidak membocorkan keberadaan data orang lain.
        """
        other_order = Order.objects.create(
            user=self.other_user, store=self.store,
            status=Order.Status.PENDING, payment_status=Order.PaymentStatus.UNPAID,
        )
        OrderShipping.objects.create(
            order=other_order, shipping_name="JNE", service_name="REG", etd="2-3",
            shipping_cost=10000, shipping_cost_net=10000, service_fee=1000,
            origin_ro=1, origin_address="Jakarta", destination_ro=2, destination_address="Cirebon",
        )
        other_item = OrderItem.objects.create(
            order=other_order, product=self.product, product_price=self.product.price, qty=1,
        )
        RefundRequest.objects.create(
            order_item=other_item,
            amount=other_item.subtotal,
            reason=RefundRequest.Reason.CUSTOMER_CANCEL,
            destination_type=RefundRequest.DestinationType.BANK,
            destination_provider=RefundRequest.Provider.BCA,
            destination_number="1234567890",
            account_holder_name="Customer Dua",
        )

        response = self.client.get(reverse("refund_request_by_item", args=[other_item.id]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)