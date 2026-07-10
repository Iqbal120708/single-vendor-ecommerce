import uuid

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


class GetOrderDetailIntegrationTest(TransactionTestCase):
    """
    Integration test untuk GetOrderDetail ("api/order/<order_id>/").

    Fokus utama: membuktikan lawan database asli bahwa satu Order bisa
    punya banyak OrderItem (checkout multi-produk, sesuai OrderService
    yang melakukan `for cart in self.carts`), dan endpoint ini WAJIB
    mengembalikan/mengarsip SEMUA item tersebut -- bukan cuma satu
    seperti pada versi lama yang pakai `.first()`.
    """

    def setUp(self):
        self.client = APIClient()

        call_command("seed_product")

        self.user = set_user()
        location_fields = set_location_fields()
        set_address(self.user, *location_fields)
        self.store = set_store(*location_fields)
        set_store_shipping_option(self.store)

        self.products = list(Product.objects.all()[:2])
        # Jaga-jaga kalau seed_product cuma bikin 1 produk, pakai produk
        # yang sama dua kali supaya test multi-item tetap bisa jalan.
        if len(self.products) < 2:
            self.products = [self.products[0], self.products[0]]

    def _create_order_with_items(
        self, user, item_count=1, order_status=Order.Status.PENDING, with_shipping=True
    ):
        order = Order.objects.create(
            user=user,
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

        items = []
        for i in range(item_count):
            product = self.products[i % len(self.products)]
            items.append(
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    product_price=product.price,
                    qty=1,
                )
            )
        return order, items

    def _detail_url(self, order_id):
        return reverse("order_detail", kwargs={"order_id": order_id})

    def test_return_404_when_order_id_not_found(self):
        """
        Test: order_id valid secara format UUID tapi tidak ada di DB.
        Assert: harus 404, bukan 500 atau data kosong yang salah bentuk.
        """
        self.client.force_authenticate(self.user)

        response = self.client.get(self._detail_url(uuid.uuid4()))

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], "Order item not found")

    def test_get_single_item_order_returns_one_item(self):
        """
        Test dasar: order dengan 1 item harus tetap jalan seperti biasa
        (baseline sebelum menguji kasus multi-item).
        """
        self.client.force_authenticate(self.user)
        order, items = self._create_order_with_items(self.user, item_count=1)

        response = self.client.get(self._detail_url(order.order_id))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["order_id"], str(order.order_id))
        self.assertEqual(len(response.data["items"]), 1)

    def test_get_multi_item_order_returns_all_items(self):
        """
        Test regresi UTAMA untuk bug `.first()` yang sudah diperbaiki.

        Skenario: satu order dengan 3 OrderItem (checkout multi-produk).
        Assert: response harus berisi SEMUA 3 item, bukan cuma 1.
        """
        self.client.force_authenticate(self.user)
        order, items = self._create_order_with_items(self.user, item_count=3)

        response = self.client.get(self._detail_url(order.order_id))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["items"]), 3)

    def test_get_items_ordered_by_created_at(self):
        """
        Test: urutan item di response harus sesuai urutan dibuat
        (created_at ascending), sesuai .order_by("created_at") yang
        ditambahkan di view.
        """
        self.client.force_authenticate(self.user)
        order, items = self._create_order_with_items(self.user, item_count=3)

        response = self.client.get(self._detail_url(order.order_id))

        returned_qtys_order = [item["product_name"] for item in response.data["items"]]
        expected_order = [item.product.name for item in items]
        self.assertEqual(returned_qtys_order, expected_order)

    def test_archived_item_excluded_but_other_items_in_same_order_still_shown(self):
        """
        Test kasus tepi: satu item di-archive, item lain dalam order
        yang sama tidak boleh ikut hilang.
        """
        self.client.force_authenticate(self.user)
        order, items = self._create_order_with_items(self.user, item_count=3)

        archived_item = items[0]
        archived_item.is_archived = True
        archived_item.save()

        response = self.client.get(self._detail_url(order.order_id))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["items"]), 2)

    def test_order_fully_archived_returns_404(self):
        """
        Test: kalau SEMUA item dalam order sudah di-archive,
        endpoint harus 404 (order dianggap tidak ada untuk user).
        """
        self.client.force_authenticate(self.user)
        order, items = self._create_order_with_items(self.user, item_count=2)

        for item in items:
            item.is_archived = True
            item.save()

        response = self.client.get(self._detail_url(order.order_id))

        self.assertEqual(response.status_code, 404)

    def test_order_from_other_user_returns_404_not_data(self):
        """
        Test: order milik user lain tidak boleh bisa diakses walau
        order_id-nya benar dan diketahui (mencegah IDOR).
        """
        other_user = set_user(
            username="other_user",
            email="other@gmail.com",
            phone_number="089384442948",
        )
        order, items = self._create_order_with_items(other_user, item_count=1)

        self.client.force_authenticate(self.user)

        response = self.client.get(self._detail_url(order.order_id))

        self.assertEqual(response.status_code, 404)

    def test_delete_archives_all_items_in_order_not_just_one(self):
        """
        Test regresi UTAMA untuk sisi delete() dari bug yang sama.

        Skenario: order dengan 3 item, panggil DELETE sekali.
        Assert: SEMUA 3 item harus jadi is_archived=True, bukan cuma 1.
        """
        self.client.force_authenticate(self.user)
        order, items = self._create_order_with_items(self.user, item_count=3)

        response = self.client.delete(self._detail_url(order.order_id))

        self.assertEqual(response.status_code, 204)

        for item in items:
            item.refresh_from_db()
            self.assertTrue(item.is_archived)

    def test_delete_then_get_returns_404(self):
        """
        Test: setelah delete (semua item ter-archive), GET ke order
        yang sama harus 404, membuktikan get() dan delete() konsisten
        memakai filter is_archived yang sama.
        """
        self.client.force_authenticate(self.user)
        order, items = self._create_order_with_items(self.user, item_count=2)

        self.client.delete(self._detail_url(order.order_id))
        response = self.client.get(self._detail_url(order.order_id))

        self.assertEqual(response.status_code, 404)

    def test_delete_order_from_other_user_returns_404(self):
        """
        Test: user tidak boleh bisa menghapus (archive) order milik
        user lain walau tahu order_id-nya.
        """
        other_user = set_user(
            username="other_user_delete",
            email="other_delete@gmail.com",
            phone_number="089384442949",
        )
        order, items = self._create_order_with_items(other_user, item_count=1)

        self.client.force_authenticate(self.user)

        response = self.client.delete(self._detail_url(order.order_id))

        self.assertEqual(response.status_code, 404)
        items[0].refresh_from_db()
        self.assertFalse(items[0].is_archived)

    def test_order_with_null_shipping_returns_404(self):
        """
        Test: order dengan shipping = None tidak boleh bisa diakses
        lewat endpoint detail, sama seperti order yang fully archived.
        """
        self.client.force_authenticate(self.user)

        order, items = self._create_order_with_items(
            self.user, item_count=1, with_shipping=False
        )

        response = self.client.get(self._detail_url(order.order_id))

        self.assertEqual(response.status_code, 404)
