from datetime import timedelta

from allauth.account.models import EmailAddress
from cart.models import Cart
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.urls import reverse
from django.utils import timezone
from order.models import CheckoutSession, Order, OrderItem
from order.tests.helper_setup import (
    set_address,
    set_location_fields,
    set_store,
    set_store_shipping_option,
    set_user,
)
from product.models import Product
from rest_framework.test import APIClient
from shipping_address.models import (
    City,
    District,
    Province,
    ShippingAddress,
    SubDistrict,
)
from store.models import Store, StoreShippingOption

User = get_user_model()


class Command(BaseCommand):
    help = "Buat checkout flow real ke dev DB untuk dapat order_id buat test webhook Midtrans"

    def handle(self, *args, **options):
        # --- hapus semua, urut dari child ke parent ---
        OrderItem.objects.all().delete()
        CheckoutSession.objects.all().delete()
        Order.objects.all().delete()
        Cart.objects.all().delete()
        Store.objects.all().delete()
        ShippingAddress.objects.all().delete()
        SubDistrict.objects.all().delete()
        District.objects.all().delete()
        City.objects.all().delete()
        Province.objects.all().delete()
        Product.objects.all().delete()
        EmailAddress.objects.all().delete()
        User.objects.all().delete()

        self.stdout.write("Semua data direset.")

        call_command("seed_product")

        client = APIClient(SERVER_NAME="localhost")

        call_command("seed_product")  # cek idempotensinya, lihat catatan di bawah

        user = set_user()
        location_fields = set_location_fields()
        shipping_address = set_address(user, *location_fields)
        store = set_store(*location_fields)
        set_store_shipping_option(store)

        cart = Cart.objects.create(user=user, product=Product.objects.first(), qty=1)

        login = client.post(
            reverse("rest_login"),
            {"email": user.email, "password": "test2938484jr"},
            format="json",
        )
        if login.status_code != 200:
            self.stderr.write(f"Login gagal: {login.data}")
            return
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        res = client.post(
            reverse("checkout"), data={"cart_ids": [cart.id]}, format="json"
        )
        self.stdout.write(f"checkout: {res.status_code} {res.data}")
        checkout_id = res.data["checkout_id"]

        res = client.post(reverse("shipping_rates"), data={"checkout_id": checkout_id})
        self.stdout.write(f"shipping_rates: {res.status_code} {res.data}")

        shipping_data = res.data["shipping_options"]["reguler"]
        del shipping_data["grandtotal"]
        shipping_data["shipping_weight"] = shipping_data.pop("weight")

        res = client.post(
            reverse("transaction"),
            data={"checkout_id": checkout_id, **shipping_data},
            format="json",
        )
        self.stdout.write(f"transaction: {res.status_code} {res.data}")

        order = Order.objects.first()
        self.stdout.write(
            f"order pk={order.pk}, order_id={getattr(order, 'order_id', None)}"
        )
