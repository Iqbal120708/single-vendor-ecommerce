from datetime import timedelta
from unittest.mock import patch

from django.core.management import call_command
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.test import APIClient

from order.models import CheckoutSession, Order, OrderItem
from cart.models import Cart
from product.models import Product
from .helper_setup import set_user, set_location_fields, set_address, set_store, set_store_shipping_option

class CheckoutTest(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.client = APIClient()

        call_command("seed_product")
        #call_command("seed_couriers")

        self.user = set_user()
        self.location_fields = set_location_fields()
        self.shipping_address = set_address(self.user, *self.location_fields)
        self.store = set_store(*self.location_fields)
        set_store_shipping_option(self.store)
        
        self.cart = Cart.objects.create(
            user=self.user,
            product=Product.objects.get(id=1),
            qty=1
        )

        self.order = Order.objects.create(
            user=self.user,
            store=self.store,
        )
        
        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.cart.product,
            product_price=self.cart.product.price,
            qty=self.cart.qty,
        )
        
        self.checkout = CheckoutSession.objects.create(
            user=self.user,
            cart_ids=[1], # product id
            destination=self.shipping_address,
            store=self.store,
            expires_at=timezone.now() + timedelta(minutes=10),
            order=self.order
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
        
    @patch("accounts.signals.logger")
    @patch("order.views_order_process.logger")
    @patch("order.views_order_process.logger_error")
    @patch("order.utils.logger")
    @patch("order.utils.logger_error")
    #@patch("order.views_order_process.fetch_shipping_rates_from_rajaongkir")
    def test(
        self,
        order_logger_error_util,
        order_log_util,
        order_logger_error_view,
        order_log_view,
        mock_logger,
    ):
        self.handle_login()
        
        res = self.client.post(reverse("shipping_rates"), data={
            "checkout_id": self.checkout.id
        })
        print(res.data)
        
        shipping_data = res.data["shipping_options"]["reguler"]
        #print(shipping_data["grandtotal"], self.cart.product.price)
        del shipping_data["grandtotal"]
        shipping_data["shipping_weight"] = shipping_data.pop("weight")
        #print(shipping_data)
        data = {
            "checkout_id": self.checkout.id,
            **shipping_data
        }
        res = self.client.post(reverse("transaction"), data=data, format="json")
        print(res.data)