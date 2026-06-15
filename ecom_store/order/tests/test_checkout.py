import uuid
from unittest.mock import patch

from cart.models import Cart
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from order.models import CheckoutSession, Order, OrderItem
from order.utils import get_destination
from product.models import Product
from rest_framework import serializers, status
from rest_framework.test import APIClient

from .helper_setup import set_address, set_location_fields, set_store, set_user


class CheckoutViewTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.url = reverse("checkout")
        call_command("seed_product")
        cls.user = set_user()
        province, city, district = set_location_fields()
        cls.shipping_address = set_address(cls.user, province, city, district)
        cls.store = set_store(province, city, district)
        cls.product = Product.objects.first()
        cls.cart = Cart.objects.create(user=cls.user, product=cls.product, qty=2)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.product.reserved_stock = 0
        self.product.save()

        self.store.is_active = True
        self.store.save()

        self.shipping_address.is_default = True
        self.shipping_address.save()

    # ------------------------------------------------------------------ #
    #  Validasi Input                                                      #
    # ------------------------------------------------------------------ #

    @patch("order.views_order_process.logger")
    def test_post_return_400_when_cart_ids_missing(self, mock_logger):
        """
        Kirim request tanpa key cart_ids sama sekali.
        Assert: status 400, response mengandung key 'cart_ids'.
        """

        res = self.client.post(self.url, data={}, format="json")

        self.assertEqual(res.status_code, 400)
        self.assertIn(
            "cart_ids harus berupa list dan tidak boleh kosong.", res.data["cart_ids"]
        )

    @patch("order.views_order_process.logger")
    def test_post_return_400_when_cart_ids_not_a_list(self, mock_logger):
        """
        Kirim cart_ids berupa integer atau string, bukan list.
        Assert: status 400, response mengandung key 'cart_ids'.
        """

        res = self.client.post(self.url, data={"cart_ids": 1}, format="json")

        self.assertEqual(res.status_code, 400)
        self.assertIn(
            "cart_ids harus berupa list dan tidak boleh kosong.", res.data["cart_ids"]
        )

    @patch("order.views_order_process.logger")
    def test_post_return_400_when_cart_ids_is_empty_list(self, mock_logger):
        """
        Kirim cart_ids berupa list kosong [].
        Assert: status 400, response mengandung key 'cart_ids'.
        """

        res = self.client.post(self.url, data={"cart_ids": []}, format="json")

        self.assertEqual(res.status_code, 400)
        self.assertIn(
            "cart_ids harus berupa list dan tidak boleh kosong.", res.data["cart_ids"]
        )

    @patch("order.views_order_process.logger")
    def test_post_return_400_when_cart_ids_contains_non_integer(self, mock_logger):
        """
        Kirim cart_ids dengan elemen bukan integer, misal ["abc", 1].
        Assert: status 400, response mengandung key 'cart_ids'.
        """

        res = self.client.post(self.url, data={"cart_ids": ["abc", 1]}, format="json")

        self.assertEqual(res.status_code, 400)
        self.assertIn(
            "Semua item di dalam cart_ids harus berupa angka (integer).",
            res.data["cart_ids"],
        )

    # ------------------------------------------------------------------ #
    #  Store                                                               #
    # ------------------------------------------------------------------ #

    @patch("order.views_order_process.logger_error")
    @patch("order.views_order_process.logger")
    def test_post_return_503_when_no_active_store(self, mock_logger, mock_logger_error):
        """
        Tidak ada store dengan is_active=True di database.
        Assert: status 503, logger_error.error() dipanggil sekali.
        """

        self.store.is_active = False
        self.store.save()

        res = self.client.post(
            self.url, data={"cart_ids": [self.cart.id]}, format="json"
        )

        self.assertEqual(res.status_code, 503)
        self.assertEqual(
            res.data["detail"], "Toko sedang tidak aktif atau tidak tersedia."
        )

        mock_logger_error.error.assert_called_once_with(
            f"Store aktif tidak ditemukan. User ID: {self.user.id}"
        )

    # ------------------------------------------------------------------ #
    #  get_destination                                                     #
    # ------------------------------------------------------------------ #

    def test_post_calls_get_destination_with_correct_args(self):
        """
        parameter mengandung shipping_address_id.
        Assert: get_destination dipanggil output shipping_address berdasarkan shipping_address_id
        """

        data = get_destination(self.user, self.shipping_address.id)

        self.assertEqual(data.id, self.shipping_address.id)

    def test_post_calls_get_destination_without_args(self):
        """
        parameter tidak mengandung shipping_address_id.
        Assert: get_destination dipanggil output shipping_address default user
        """

        data = get_destination(self.user)

        self.assertTrue(data.is_default)

    @patch("order.utils.logger")
    def test_post_return_400_when_shipping_address_id_not_found(self, mock_logger):
        """
        shipping_address_id dikirim tapi tidak ada di database milik user.
        Assert: status 400, response mengandung key 'detail'
        dengan pesan 'Alamat pengiriman tidak ditemukan.'
        """

        with self.assertRaises(serializers.ValidationError) as ctx:
            get_destination(self.user, shipping_address_id=9999)

        self.assertEqual(
            ctx.exception.detail, {"detail": "Alamat pengiriman tidak ditemukan."}
        )

        mock_logger.warning.assert_called_once_with(
            f"Shipping address tidak ditemukan. User ID: {self.user.id}, Address ID: 9999"
        )

    @patch("order.utils.logger")
    def test_post_return_400_when_no_default_address(self, mock_logger):
        """
        shipping_address_id tidak dikirim dan user tidak punya default address.
        Assert: status 400, response mengandung key 'detail'
        dengan pesan 'Belum ada alamat pengiriman. Silakan tambahkan alamat terlebih dahulu.'
        """

        self.shipping_address.is_default = False
        self.shipping_address.save()

        with self.assertRaises(serializers.ValidationError) as ctx:
            get_destination(self.user)

        self.assertEqual(
            ctx.exception.detail,
            {
                "detail": "Belum ada alamat pengiriman. Silakan tambahkan alamat terlebih dahulu."
            },
        )

        mock_logger.warning.assert_called_once_with(
            f"Default address tidak ditemukan. User ID: {self.user.id}"
        )

    # ------------------------------------------------------------------ #
    #  Cart
    # ------------------------------------------------------------------ #

    @patch("order.views_order_process.logger_error")
    @patch("order.views_order_process.logger")
    def test_post_return_400_when_cart_ids_not_found(
        self, mock_logger, mock_logger_error
    ):
        """
        cart_ids berisi ID yang tidak ada di database milik user.
        Assert: status 400, response mengandung key 'cart_ids' dengan pesan cart tidak ditemukan, logger_error.error() dipanggil.
        """
        res = self.client.post(
            reverse("checkout"),
            data={
                "cart_ids": [self.cart.id, 9999],
            },
            format="json",
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Cart IDs not found: [9999]", res.data["cart_ids"])

        mock_logger_error.error.assert_called_once()

    # ------------------------------------------------------------------ #
    #  Validasi Stock
    # ------------------------------------------------------------------ #

    @patch("order.views_order_process.logger_error")
    @patch("order.views_order_process.logger")
    def test_post_return_500_when_stock_not_enough(
        self, mock_logger, mock_logger_error
    ):
        """
        product.stock - product.reserved_stock < cart.qty.
        Assert: status 400, logger_error.error() dipanggil,
        CheckoutSession tidak created di database (atomic rollback).
        """

        self.cart.qty = 999
        self.cart.save()

        res = self.client.post(
            self.url, data={"cart_ids": [self.cart.id]}, format="json"
        )

        self.assertEqual(res.status_code, 400)
        self.assertEqual(
            res.data["detail"], f"Stok {self.cart.product.name} tidak cukup"
        )

        mock_logger_error.error.assert_called_once()

        # atomic rollback — CheckoutSession tidak terbuat
        self.assertFalse(CheckoutSession.objects.exists())

    @patch("order.services.checkout.OrderService")
    @patch("order.views_order_process.logger_error")
    @patch("order.views_order_process.logger")
    def test_post_return_500_when_order_service_raises(
        self, mock_logger, mock_logger_error, mock_order_service
    ):
        """
        OrderService.execute() raise Exception.
        Assert: status 500, logger_error.error() dipanggil,
        CheckoutSession tidak created (atomic rollback),
        reserved_stock tidak berubah.
        """
        mock_order_service.return_value.execute.side_effect = Exception(
            "unexpected error"
        )

        res = self.client.post(
            self.url,
            data={"cart_ids": [self.cart.id]},
            format="json",
        )

        self.assertEqual(res.status_code, 500)

        mock_logger_error.error.assert_called_once_with(
            f"Gagal membuat order untuk user {self.user.id}: unexpected error",
        )

        # atomic rollback — CheckoutSession tidak terbuat
        self.assertFalse(CheckoutSession.objects.exists())

        # reserved_stock tidak berubah
        product = self.cart.product
        product.refresh_from_db()
        self.assertEqual(product.reserved_stock, 0)

    @patch("order.views_order_process.logger")
    def test_post_reserved_stock_incremented_after_checkout(self, mock_logger):
        """
        Stock cukup, seluruh flow checkout berhasil.
        Assert: product.reserved_stock di database bertambah sebesar cart.qty.
        """

        res = self.client.post(
            self.url, data={"cart_ids": [self.cart.id]}, format="json"
        )

        self.assertEqual(self.cart.qty, 2)

        product = self.cart.product

        self.assertEqual(product.reserved_stock, 0)

        product.refresh_from_db()
        self.assertEqual(product.reserved_stock, 2)  # +2

    # ------------------------------------------------------------------ #
    #  Happy Path                                                          #
    # ------------------------------------------------------------------ #

    @patch("order.views_order_process.logger_error")
    @patch("order.views_order_process.logger")
    def test_post_return_200_with_checkout_id_when_success(
        self, mock_logger, mock_logger_error
    ):
        """
        Semua kondisi normal: store aktif, stock cukup, order terbuat.
        Assert: status 200, response body mengandung key 'checkout_id'
        berupa string UUID dari CheckoutSession yang dibuat.
        """

        res = self.client.post(
            self.url,
            data={
                "cart_ids": [self.cart.id],
            },
            format="json",
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("checkout_id", res.data)

        # pastikan checkout_id adalah UUID valid
        checkout = CheckoutSession.objects.get(id=res.data["checkout_id"])
        self.assertEqual(str(checkout.id), res.data["checkout_id"])

    @patch("order.views_order_process.logger_error")
    @patch("order.views_order_process.logger")
    def test_post_order_and_order_items_created_when_success(
        self, mock_logger, mock_logger_error
    ):
        """
        Seluruh flow checkout berhasil.
        Assert: Order terbuat di database dengan user dan store yang benar,
        OrderItem terbuat untuk setiap cart dengan qty dan price yang sesuai.
        """

        res = self.client.post(
            self.url,
            data={
                "cart_ids": [self.cart.id],
            },
            format="json",
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)

        order = Order.objects.filter(user=self.user, store=self.store).first()
        self.assertIsNotNone(order)
        self.assertEqual(order.user, self.user)
        self.assertEqual(order.store, self.store)

        order_item = OrderItem.objects.filter(order=order)
        self.assertEqual(order_item.count(), 1)

        item = order_item.first()
        self.assertEqual(item.qty, self.cart.qty)
        self.assertEqual(item.product_price, self.cart.product.price)

    @patch("order.views_order_process.logger_error")
    @patch("order.views_order_process.logger")
    def test_post_logger_info_called_twice_on_success(
        self, mock_logger, mock_logger_error
    ):
        """
        Checkout berhasil sampai response 200.
        Assert: logger.info() dipanggil minimal 2 kali —
        sekali saat awal request masuk, sekali setelah checkout session dibuat.
        """

        res = self.client.post(
            self.url,
            data={
                "cart_ids": [self.cart.id],
            },
            format="json",
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(mock_logger.info.call_count, 2)

        checkout_id = res.data["checkout_id"]

        mock_logger.info.assert_any_call(
            f"User {self.user.id} memulai checkout untuk cart_ids: {[self.cart.id]}"
        )
        mock_logger.info.assert_any_call(
            f"Checkout Session {checkout_id} dibuat untuk User {self.user.id}. Data disimpan di model."
        )
