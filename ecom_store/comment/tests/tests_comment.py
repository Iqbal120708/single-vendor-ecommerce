from comment.models import Comment
from django.core.management import call_command
from django.test import TransactionTestCase
from django.urls import reverse
from freezegun import freeze_time
from order.models import Order, OrderItem
from order.tests.helper_setup import (
    set_address,
    set_location_fields,
    set_store,
    set_store_shipping_option,
    set_user,
)
from product.models import Product
from rest_framework.test import APIClient


class CommentIntegrationTest(TransactionTestCase):
    """
    Integration test untuk CommentView ("api/comment/<product_id>/").

    Cakupan:
    1. User hanya boleh comment produk yang sudah dibeli & delivered.
    2. Duplicate comment aktif ditolak 400, bukan 500 IntegrityError.
    3. Comment yang di-archive bisa dihidupkan lagi via POST baru
       (reuse row, bukan bikin baru) karena unique_together (user,
       product) tidak membedakan archived/tidak.
    4. Window edit 24 jam (is_editable()) pakai freeze_time.
    5. Comment archived tidak bisa di-PUT/DELETE lagi (404).
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
        self.other_product = Product.objects.exclude(id=self.product.id).first()

    def _comment_url(self, product_id):
        return reverse("comment", args=[product_id])

    def _create_delivered_order_item(self, user, product):
        order = Order.objects.create(
            user=user,
            store=self.store,
            status=Order.Status.DELIVERED,
            payment_status=Order.PaymentStatus.PAID,
        )
        return OrderItem.objects.create(
            order=order,
            product=product,
            product_price=product.price,
            qty=1,
        )

    def _create_undelivered_order_item(self, user, product, order_status):
        order = Order.objects.create(
            user=user,
            store=self.store,
            status=order_status,
            payment_status=Order.PaymentStatus.PAID,
        )
        return OrderItem.objects.create(
            order=order,
            product=product,
            product_price=product.price,
            qty=1,
        )

    # --- GET ---

    def test_get_returns_only_non_archived_comments_for_the_product(self):
        """GET hanya balikin comment aktif milik user untuk produk itu."""
        self.client.force_authenticate(self.user)

        other_user = set_user(
            username="other_user_get",
            email="other_get@gmail.com",
            phone_number="089384442950",
        )

        Comment.objects.create(
            user=self.user, product=self.product, content="bagus", rating=5
        )
        Comment.objects.create(
            user=other_user,
            product=self.product,
            content="arsip",
            rating=1,
            is_archived=True,
        )
        # Comment di produk lain tidak boleh ikut muncul
        Comment.objects.create(
            user=self.user, product=self.other_product, content="lain", rating=3
        )

        response = self.client.get(self._comment_url(self.product.id))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["content"], "bagus")

    # --- POST ---

    def test_post_returns_404_when_product_not_found(self):
        self.client.force_authenticate(self.user)

        response = self.client.post(
            self._comment_url(99999),
            data={"rating": 5, "content": "test"},
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], "Product not found")

    def test_post_returns_403_when_user_never_purchased_product(self):
        """User belum pernah beli produk ini sama sekali."""
        self.client.force_authenticate(self.user)

        response = self.client.post(
            self._comment_url(self.product.id),
            data={"rating": 5, "content": "test"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["detail"], "User belum pernah membeli product")

    def test_post_returns_403_when_order_not_yet_delivered(self):
        """
        Sudah checkout & bayar, tapi order belum delivered -> tetap
        403, membuktikan check-nya spesifik "delivered", bukan cuma
        "pernah checkout".
        """
        self.client.force_authenticate(self.user)
        self._create_undelivered_order_item(
            self.user, self.product, Order.Status.SHIPPED
        )

        response = self.client.post(
            self._comment_url(self.product.id),
            data={"rating": 5, "content": "test"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_post_returns_201_when_order_delivered(self):
        """User sudah beli & order delivered -> boleh comment."""
        self.client.force_authenticate(self.user)
        self._create_delivered_order_item(self.user, self.product)

        response = self.client.post(
            self._comment_url(self.product.id),
            data={"rating": 5, "content": "produk bagus"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Comment.objects.count(), 1)
        comment = Comment.objects.first()
        self.assertEqual(comment.user, self.user)
        self.assertEqual(comment.product, self.product)

    def test_post_duplicate_comment_same_product_returns_400(self):
        """Comment kedua ke produk sama (yang pertama masih aktif) -> 400 rapi, bukan 500."""
        self.client.force_authenticate(self.user)
        self._create_delivered_order_item(self.user, self.product)

        first_response = self.client.post(
            self._comment_url(self.product.id),
            data={"rating": 5, "content": "pertama"},
            format="json",
        )
        self.assertEqual(first_response.status_code, 201)

        second_response = self.client.post(
            self._comment_url(self.product.id),
            data={"rating": 4, "content": "kedua"},
            format="json",
        )

        self.assertEqual(second_response.status_code, 400)
        self.assertEqual(Comment.objects.count(), 1)

    def test_post_after_delete_reuses_archived_row_instead_of_creating_new(self):
        """
        Test regresi: comment lalu delete (soft-delete), lalu comment
        lagi ke produk yang sama harus 201 dan reuse row lama
        (unarchive + update), bukan bikin row baru.
        """
        self.client.force_authenticate(self.user)
        self._create_delivered_order_item(self.user, self.product)

        first_response = self.client.post(
            self._comment_url(self.product.id),
            data={"rating": 5, "content": "pertama"},
            format="json",
        )
        self.assertEqual(first_response.status_code, 201)
        original_comment_id = Comment.objects.get(
            user=self.user, product=self.product
        ).id

        delete_response = self.client.delete(self._comment_url(self.product.id))
        self.assertEqual(delete_response.status_code, 204)

        second_response = self.client.post(
            self._comment_url(self.product.id),
            data={"rating": 3, "content": "komentar baru setelah dihapus"},
            format="json",
        )

        self.assertEqual(second_response.status_code, 201)
        self.assertEqual(Comment.objects.count(), 1)

        comment = Comment.objects.get(user=self.user, product=self.product)
        self.assertEqual(comment.id, original_comment_id)
        self.assertFalse(comment.is_archived)
        self.assertEqual(comment.content, "komentar baru setelah dihapus")
        self.assertEqual(comment.rating, 3)

    # --- PUT ---

    def test_put_returns_404_when_comment_not_found(self):
        self.client.force_authenticate(self.user)

        response = self.client.put(
            self._comment_url(self.product.id),
            data={"rating": 3, "content": "update"},
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], "Comment not found")

    def test_put_returns_200_and_updates_within_edit_window(self):
        """Comment masih bisa diedit dalam 24 jam pertama."""
        with freeze_time("2025-01-01T10:00:00+07:00"):
            self.client.force_authenticate(self.user)
            Comment.objects.create(
                user=self.user, product=self.product, content="awal", rating=2
            )

            response = self.client.put(
                self._comment_url(self.product.id),
                data={"rating": 4, "content": "sudah diedit"},
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        comment = Comment.objects.get(user=self.user, product=self.product)
        self.assertEqual(comment.content, "sudah diedit")
        self.assertEqual(comment.rating, 4)

    def test_put_returns_403_after_24_hour_edit_window(self):
        """Test regresi is_editable(): edit 2 hari setelah dibuat harus 403."""
        with freeze_time("2025-01-01T10:00:00+07:00"):
            Comment.objects.create(
                user=self.user, product=self.product, content="awal", rating=2
            )

        with freeze_time("2025-01-03T10:00:00+07:00"):
            self.client.force_authenticate(self.user)
            response = self.client.put(
                self._comment_url(self.product.id),
                data={"rating": 4, "content": "coba edit"},
                format="json",
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.data["detail"],
            "Komentar sudah tidak bisa diedit setelah 24 jam",
        )

    # --- DELETE ---

    def test_delete_returns_404_when_comment_not_found(self):
        self.client.force_authenticate(self.user)

        response = self.client.delete(self._comment_url(self.product.id))

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], "Comment not found")

    def test_delete_archives_comment_not_hard_delete(self):
        """Delete adalah soft-delete (is_archived=True), row tetap ada di DB."""
        self.client.force_authenticate(self.user)
        comment = Comment.objects.create(
            user=self.user, product=self.product, content="mau dihapus", rating=3
        )

        response = self.client.delete(self._comment_url(self.product.id))

        self.assertEqual(response.status_code, 204)
        comment.refresh_from_db()
        self.assertTrue(comment.is_archived)
        self.assertTrue(Comment.objects.filter(id=comment.id).exists())

    def test_archived_comment_excluded_from_get_and_not_editable_via_put(self):
        """
        Comment archived tidak muncul di GET dan tidak bisa diedit via
        PUT (404) -- satu-satunya jalan comment lagi adalah POST baru,
        yang akan reuse & unarchive row.
        """
        self.client.force_authenticate(self.user)
        comment = Comment.objects.create(
            user=self.user,
            product=self.product,
            content="sudah diarsip",
            rating=2,
            is_archived=True,
        )

        get_response = self.client.get(self._comment_url(self.product.id))
        self.assertEqual(len(get_response.data), 0)

        put_response = self.client.put(
            self._comment_url(self.product.id),
            data={"rating": 5, "content": "coba edit comment archived"},
            format="json",
        )
        self.assertEqual(put_response.status_code, 404)

        comment.refresh_from_db()
        self.assertEqual(comment.content, "sudah diarsip")

    def test_delete_twice_returns_404_on_second_call(self):
        """Delete comment yang sama dua kali -- percobaan kedua harus 404."""
        self.client.force_authenticate(self.user)
        Comment.objects.create(
            user=self.user, product=self.product, content="mau dihapus", rating=3
        )

        first_delete = self.client.delete(self._comment_url(self.product.id))
        self.assertEqual(first_delete.status_code, 204)

        second_delete = self.client.delete(self._comment_url(self.product.id))
        self.assertEqual(second_delete.status_code, 404)
