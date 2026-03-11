import uuid
from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse
from freezegun import freeze_time
from rest_framework.test import APITestCase

from cart.models import Cart
from order.models import OrderItem
from product.models import Product
from store.models import Store

User = get_user_model()


class BaseTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        # self.client = APIClient()
        call_command("seed_product")
        call_command("seed_couriers")
        call_command("data_test_user")
        call_command("data_test_store")

        cls.user1 = User.objects.get(email="test@gmail.com")
        cls.user2 = User.objects.create_user(
            username="test2",
            email="test2@gmail.com",
            password="test2938484jr",
            phone_number="089612346789",
        )
        EmailAddress.objects.create(
            user=cls.user2, email=cls.user2.email, verified=True, primary=True
        )

        cls.store = Store.objects.get(email="store@gmail.com")

        cls.cart = Cart.objects.create(
            user=cls.user1, product=Product.objects.first(), qty=1
        )

    def handle_login(self, user):
        login = self.client.post(
            reverse("rest_login"),
            {"email": user.email, "password": "test2938484jr"},
            format="json",
        )

        self.assertEqual(login.status_code, 200)

        token = login.data["access"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def create_order_transaction(self):
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


@freeze_time("2025-03-07T20:43:00+07:00")
@patch("accounts.signals.logger")
@patch("order.views_order_process.logger")
@patch("order.views_order_process.logger_error")
@patch("order.utils.logger")
@patch("order.utils.logger_error")
class TestGetOrder(BaseTestCase):
    def test_get_order_return_data_if_request_with_status_parameter_by_user1(
        self,
        order_logger_error_util,
        order_log_util,
        order_logger_error_view,
        order_log_view,
        mock_logger,
    ):
        self.handle_login(self.user1)
        self.create_order_transaction()

        res = self.client.get("/api/order/?status=pending")

        self.assertEqual(res.status_code, 200)

        self.assertEqual(len(res.data), 1)
        self.assertTrue(res.data[0]["order_id"])

    def test_get_order_return_data_if_request_with_paymentstatus_parameter_by_user1(
        self,
        order_logger_error_util,
        order_log_util,
        order_logger_error_view,
        order_log_view,
        mock_logger,
    ):
        self.handle_login(self.user1)
        self.create_order_transaction()

        res = self.client.get("/api/order/?payment_status=unpaid")

        self.assertEqual(res.status_code, 200)

        self.assertEqual(len(res.data), 1)
        self.assertTrue(res.data[0]["order_id"])

    def test_get_order_return_empty_data_if_request_by_user2(
        self,
        order_logger_error_util,
        order_log_util,
        order_logger_error_view,
        order_log_view,
        mock_logger,
    ):
        """
        Request with status and payment status filter
        """

        self.handle_login(self.user1)
        self.create_order_transaction()

        self.handle_login(self.user2)

        # Request by status
        res = self.client.get("/api/order/?status=pending")

        self.assertEqual(res.status_code, 200)

        self.assertEqual(len(res.data), 0)

        # Request by payment status
        res = self.client.get("/api/order/?payment_status=unpaid")

        self.assertEqual(res.status_code, 200)

        self.assertEqual(len(res.data), 0)

    def test_get_order_return_404_if_request_not_parameter(
        self,
        order_logger_error_util,
        order_log_util,
        order_logger_error_view,
        order_log_view,
        mock_logger,
    ):
        self.handle_login(self.user1)
        self.create_order_transaction()

        res = self.client.get("/api/order/")

        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["detail"], "Filter parameter required.")

    def test_get_order_return_empty_data_if_order_data_is_archived(
        self,
        order_logger_error_util,
        order_log_util,
        order_logger_error_view,
        order_log_view,
        mock_logger,
    ):
        self.handle_login(self.user1)
        self.create_order_transaction()

        order_item = OrderItem.objects.first()
        order_item.is_archived = True
        order_item.save()

        res = self.client.get("/api/order/?status=pending")

        self.assertEqual(res.status_code, 200)

        self.assertEqual(len(res.data), 0)


@freeze_time("2025-03-07T20:43:00+07:00")
@patch("accounts.signals.logger")
@patch("order.views_order_process.logger")
@patch("order.views_order_process.logger_error")
@patch("order.utils.logger")
@patch("order.utils.logger_error")
class TestGetOrderDetail(BaseTestCase):
    def test_get_order_detail_return_data_if_request_success(
        self,
        order_logger_error_util,
        order_log_util,
        order_logger_error_view,
        order_log_view,
        mock_logger,
    ):
        self.handle_login(self.user1)
        self.create_order_transaction()

        res = self.client.get("/api/order/?status=pending")
        order_id = res.data[0]["order_id"]

        res_detail = self.client.get(reverse("order_detail", args=[order_id]))

        self.assertEqual(res_detail.status_code, 200)

        self.assertEqual(res_detail.data["order_id"], order_id)
        self.assertEqual(res_detail.data["status"], "pending")
        self.assertEqual(res_detail.data["payment_status"], "unpaid")
        self.assertTrue(res_detail.data["created_at"])
        self.assertTrue(res_detail.data["orderitem_created_at"])

    def test_get_order_detail_return_404_if_request_order_not_found(
        self,
        order_logger_error_util,
        order_log_util,
        order_logger_error_view,
        order_log_view,
        mock_logger,
    ):
        self.handle_login(self.user1)

        order_id = uuid.uuid4()
        res_detail = self.client.get(reverse("order_detail", args=[order_id]))

        self.assertEqual(res_detail.status_code, 404)
        self.assertEqual(res_detail.data["detail"], "Order item not found")

    def test_get_order_detail_return_404_if_order_data_is_archived(
        self,
        order_logger_error_util,
        order_log_util,
        order_logger_error_view,
        order_log_view,
        mock_logger,
    ):
        self.handle_login(self.user1)
        self.create_order_transaction()

        order_item = OrderItem.objects.first()
        order_item.is_archived = True
        order_item.save()

        order_id = order_item.order.order_id
        res_detail = self.client.get(reverse("order_detail", args=[order_id]))

        self.assertEqual(res_detail.status_code, 404)
        self.assertEqual(res_detail.data["detail"], "Order item not found")

    def test_get_order_detail_return_404_if_data_order_id_has_user1_but_request_by_user2(
        self,
        order_logger_error_util,
        order_log_util,
        order_logger_error_view,
        order_log_view,
        mock_logger,
    ):
        self.handle_login(self.user1)
        self.create_order_transaction()

        order_item = OrderItem.objects.first()
        order_id = order_item.order.order_id

        # order has user1
        self.assertEqual(order_item.order.user, self.user1)

        # Request by user2
        self.handle_login(self.user2)

        res_detail = self.client.get(reverse("order_detail", args=[order_id]))

        self.assertEqual(res_detail.status_code, 404)
        self.assertEqual(res_detail.data["detail"], "Order item not found")

    def test_delete_order_return_204_if_success(
        self,
        order_logger_error_util,
        order_log_util,
        order_logger_error_view,
        order_log_view,
        mock_logger,
    ):
        self.handle_login(self.user1)
        self.create_order_transaction()

        order_item = OrderItem.objects.first()
        order_id = order_item.order.order_id

        res_detail = self.client.delete(reverse("order_detail", args=[order_id]))

        self.assertEqual(res_detail.status_code, 204)

    def test_delete_order_return_404_if_order_item_not_found(
        self,
        order_logger_error_util,
        order_log_util,
        order_logger_error_view,
        order_log_view,
        mock_logger,
    ):
        self.handle_login(self.user1)
        self.create_order_transaction()

        # Use a random UUID to test a not found response
        order_id = uuid.uuid4()
        res_detail = self.client.delete(reverse("order_detail", args=[order_id]))

        self.assertEqual(res_detail.status_code, 404)
        self.assertEqual(res_detail.data["detail"], "Order item not found")
