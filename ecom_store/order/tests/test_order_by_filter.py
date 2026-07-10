from django.core.management import call_command
from django.test import TransactionTestCase
from django.urls import reverse
from order.models import Order, OrderItem, OrderShipping
from product.models import Product
from rest_framework.test import APIClient

from .helper_setup import (
    set_address,
    set_location_fields,
    set_store,
    set_store_shipping_option,
    set_user,
)


class GetOrderByFilterIntegrationTest(TransactionTestCase):
    """
    Integration test untuk endpoint GetOrderByFilter ("api/order/").

    Fokus test ini BUKAN mengulang semua kombinasi filter secara unit,
    tapi membuktikan lawan database asli bahwa:
    1. Filter status dan payment_status digabung sebagai AND, bukan
       saling menimpa (ini bug yang sudah diperbaiki dari `elif` -> AND).
    2. Data milik user lain dan item yang sudah di-archive tidak pernah
       ikut ke luar dari endpoint ini, walau parameter filter cocok.
    """

    def setUp(self):
        self.client = APIClient()

        call_command("seed_product")

        self.user = set_user()
        location_fields = set_location_fields()
        set_address(self.user, *location_fields)
        self.store = set_store(*location_fields)
        set_store_shipping_option(self.store)

        self.product = Product.objects.first()
        self.url = reverse("order")

    def _create_order_item(
        self, user, order_status, payment_status, is_archived=False, with_shipping=True
    ):
        order = Order.objects.create(
            user=user,
            store=self.store,
            status=order_status,
            payment_status=payment_status,
            payment_method=Order.PaymentMethod.COD,
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
    
        return OrderItem.objects.create(
            order=order,
            product=self.product,
            product_price=self.product.price,
            qty=1,
            is_archived=is_archived,
        )

    def test_return_400_when_no_filter_parameter_given(self):
        """
        Test: request tanpa query param status maupun payment_status.
        Assert: harus 400, bukan mengembalikan semua order milik user
        (mencegah endpoint ini diam-diam jadi "get all orders").
        """
        self.client.force_authenticate(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Filter parameter required.")

    def test_filter_by_status_only(self):
        """
        Test: filter pakai status saja.
        Assert: hanya order dengan status yang cocok yang muncul.
        """
        self.client.force_authenticate(self.user)

        shipped_item = self._create_order_item(
            self.user, Order.Status.SHIPPED, Order.PaymentStatus.PAID
        )
        self._create_order_item(
            self.user, Order.Status.PENDING, Order.PaymentStatus.PAID
        )

        response = self.client.get(self.url, {"status": Order.Status.SHIPPED})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["order_id"], str(shipped_item.order.order_id))

    def test_filter_by_payment_status_only(self):
        """
        Test: filter pakai payment_status saja.
        Assert: hanya order dengan payment_status yang cocok yang muncul.
        """
        self.client.force_authenticate(self.user)

        paid_item = self._create_order_item(
            self.user, Order.Status.PROCESSING, Order.PaymentStatus.PAID
        )
        self._create_order_item(
            self.user, Order.Status.PROCESSING, Order.PaymentStatus.UNPAID
        )

        response = self.client.get(
            self.url, {"payment_status": Order.PaymentStatus.PAID}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["order_id"], str(paid_item.order.order_id))

    def test_filter_by_status_and_payment_status_combined_returns_intersection(self):
        """
        Test regresi untuk bug `elif` yang sudah diperbaiki.

        Skenario: ada 3 order dengan kombinasi status/payment_status
        berbeda. Hanya SATU yang cocok di KEDUA filter sekaligus.

        Assert: response harus berisi irisan (AND), bukan salah satu
        filter menang sendirian seperti pada versi lama (`elif`).
        """
        self.client.force_authenticate(self.user)

        matching_item = self._create_order_item(
            self.user, Order.Status.SHIPPED, Order.PaymentStatus.PAID
        )
        # Status cocok, payment_status tidak -> harus dikecualikan
        self._create_order_item(
            self.user, Order.Status.SHIPPED, Order.PaymentStatus.UNPAID
        )
        # payment_status cocok, status tidak -> harus dikecualikan
        self._create_order_item(
            self.user, Order.Status.PENDING, Order.PaymentStatus.PAID
        )

        response = self.client.get(
            self.url,
            {
                "status": Order.Status.SHIPPED,
                "payment_status": Order.PaymentStatus.PAID,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]["order_id"], str(matching_item.order.order_id)
        )

    def test_archived_order_item_excluded_even_if_filter_matches(self):
        """
        Test: order item dengan is_archived=True tidak boleh muncul,
        walau status dan payment_status-nya cocok dengan filter.
        """
        self.client.force_authenticate(self.user)

        self._create_order_item(
            self.user,
            Order.Status.SHIPPED,
            Order.PaymentStatus.PAID,
            is_archived=True,
        )

        response = self.client.get(self.url, {"status": Order.Status.SHIPPED})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    def test_order_item_from_other_user_excluded(self):
        """
        Test: order item milik user lain tidak boleh ikut muncul,
        walau status dan payment_status-nya cocok dengan filter.
        Ini membuktikan scoping request.user benar-benar jalan,
        bukan cuma filter status/payment_status saja.
        """
        other_user = set_user(
            username="other_user",
            email="other@gmail.com",
            phone_number="089384442948",
        )

        self.client.force_authenticate(self.user)

        self._create_order_item(
            other_user, Order.Status.SHIPPED, Order.PaymentStatus.PAID
        )

        response = self.client.get(self.url, {"status": Order.Status.SHIPPED})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)
        
    def test_order_with_null_shipping_excluded(self):
        """
        Test: order item dengan order.shipping = None tidak boleh muncul,
        walau status dan payment_status-nya cocok dengan filter.
        Ini membuktikan .exclude(order__shipping__isnull=True) benar-benar
        jalan, bukan cuma lolos karena kebetulan filter lain menyaring duluan.
        """
        self.client.force_authenticate(self.user)

        # order.shipping tidak di-set -> None
        self._create_order_item(
            self.user, Order.Status.PENDING, Order.PaymentStatus.PENDING, with_shipping=False
        )

        response = self.client.get(self.url, {"status": Order.Status.PENDING})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)