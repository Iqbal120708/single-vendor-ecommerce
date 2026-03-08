from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.management import call_command
from freezegun import freeze_time
from cart.models import Cart
from product.models import Product
from store.models import Store
from comment.models import Comment
from order.models import OrderItem
from unittest.mock import patch
#from rest_framework.test import APIClient
from rest_framework.test import APITestCase

#from django.test import TransactionTestCase

User = get_user_model()

@freeze_time("2025-03-07T20:43:00+07:00")
@patch("accounts.signals.logger")
@patch("order.views.logger")
@patch("order.views.logger_error")
@patch("order.utils.logger")
@patch("order.utils.logger_error")
class TransactionTest(APITestCase):
    #reset_sequences = True
    @classmethod
    def setUpTestData(cls):
        #self.client = APIClient()
        call_command("seed_product")
        call_command("seed_couriers")
        call_command("data_test_user")
        call_command("data_test_store")

        cls.user = User.objects.get(email="test@gmail.com")
        cls.store = Store.objects.get(email="store@gmail.com")
        
        cls.cart = Cart.objects.create(
            user=cls.user,
            product=Product.objects.get(id=1),
            qty=1
        )
        
        cls.comment = Comment.objects.create(
            product=Product.objects.get(id=2),
            user=cls.user,
            content="Test Comment",
            rating=1
        )
        
        
    def handle_login(self):
        login = self.client.post(
            reverse("rest_login"),
            {"email": self.user.email, "password": "test2938484jr"},
            format="json",
        )

        self.assertEqual(login.status_code, 200)

        token = login.data["access"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


    def create_order_transaction(
        self
        
    ):
        self.handle_login()

        # checkout
        res_checkout = self.client.post(
            reverse("checkout"), data={"cart_ids": [self.cart.id]}, format="json"
        )

        # transaction
        data = {
            "checkout_id": res_checkout.data["checkout_id"],
            "code": res_checkout.data["shipping_options"][0]["code"],
            "service": res_checkout.data["shipping_options"][0]["service"],
            "cost": res_checkout.data["shipping_options"][0]["cost"],
        }
        res = self.client.post(reverse("transaction"), data=data, format="json")
        
    def test_get(
        self,
        order_logger_error_util,
        order_log_util,
        order_logger_error_view,
        order_log_view,
        mock_logger,
    ):
        self.handle_login()
        res = self.client.get(
            reverse("comment", args=[2])
        )
        
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["username"], "test")

        
    def test_create_comment_returns_404_if_product_not_found(
        self,
        order_logger_error_util,
        order_log_util,
        order_logger_error_view,
        order_log_view,
        mock_logger,
    ):
        self.handle_login()
        
        res = self.client.post(
            reverse("comment", args=[99]), data={
                "rating": 3,
                "content": "test comment"
            }
        )
        
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.data["detail"], "Product not found")
    
    def test_create_comment_returns_403_if_no_purchase(
        self,
        order_logger_error_util,
        order_log_util,
        order_logger_error_view,
        order_log_view,
        mock_logger,
    ):
        self.handle_login()
        
        res = self.client.post(
            reverse("comment", args=[3]), data={
                "rating": 3,
                "content": "test update comment"
            }
        )
    
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data["detail"], "User belum pernah membeli product")
        
    def test_create_comment_returns_201_if_success(
        self,
        order_logger_error_util,
        order_log_util,
        order_logger_error_view,
        order_log_view,
        mock_logger,
    ):
        self.handle_login()
        
        self.create_order_transaction()
        
        self.assertEqual(OrderItem.objects.count(), 1)
        
        order_item = OrderItem.objects.first()
        
        order = order_item.order
        order.status = "delivered"
        order.payment_status = "paid"
        order.save()
        
        res = self.client.post(
            reverse("comment", args=[order_item.product.id]), data={
                "rating": 3,
                "content": "test comment"
            }
        )
    
        self.assertEqual(res.status_code, 201)
        
        queryset = Comment.objects.count()
        self.assertEqual(queryset, 2)
        
    def test_update_comment_returns_404_if_comment_not_found(
        self,
        order_logger_error_util,
        order_log_util,
        order_logger_error_view,
        order_log_view,
        mock_logger,
    ):
        self.handle_login()
        
        res = self.client.put(
            reverse("comment", args=[99]), data={
                "rating": 3,
                "content": "test upddate comment"
            }
        )
        
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.data["detail"], "Comment not found")
    
    @freeze_time("2025-03-09T20:43:00+07:00") # loncat 2 hari dari tanggal freeze_time class
    def test_update_comment_returns_403_if_exceeding_time_limit(
        self,
        order_logger_error_util,
        order_log_util,
        order_logger_error_view,
        order_log_view,
        mock_logger,
    ):
        self.handle_login()
        
        res = self.client.put(
            reverse("comment", args=[2]), data={
                "rating": 3,
                "content": "test update comment"
            }
        )
        
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data["detail"], "Komentar sudah tidak bisa diedit setelah 24 jam")
    
    def test_update_comment_returns_200_if_success(
        self,
        order_logger_error_util,
        order_log_util,
        order_logger_error_view,
        order_log_view,
        mock_logger,
    ):
        self.handle_login()
        
        res = self.client.put(
            reverse("comment", args=[2]), data={
                "rating": 3,
                "content": "test update comment"
            }
        )
    
        self.assertEqual(res.status_code, 200)
        
        # previous data
        self.assertEqual(self.comment.rating, 1)
        self.assertEqual(self.comment.content, "Test Comment")
        
        # new data
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.rating, 3)
        self.assertEqual(self.comment.content, "test update comment")
        
    def test_delete_comment_returns_404_if_comment_not_found(
        self,
        order_logger_error_util,
        order_log_util,
        order_logger_error_view,
        order_log_view,
        mock_logger,
    ):
        self.handle_login()
        
        res = self.client.delete(
            reverse("comment", args=[99])
        )
        
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.data["detail"], "Comment not found")
    
    def test_delete_comment_returns_204_if_no_content(
        self,
        order_logger_error_util,
        order_log_util,
        order_logger_error_view,
        order_log_view,
        mock_logger,
    ):
        self.handle_login()
        
        res = self.client.delete(
            reverse("comment", args=[2])
        )
        
        self.assertEqual(res.status_code, 204)
        
        # previous data
        self.assertFalse(self.comment.is_archived)
        
        # new data
        self.comment.refresh_from_db()
        self.assertTrue(self.comment.is_archived)
    