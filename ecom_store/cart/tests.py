#from rest_framework.test import APITestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from allauth.account.models import EmailAddress
from unittest.mock import patch
from django.core.management import call_command
from freezegun import freeze_time
from django.db import connection
from .models import Cart
from django.test import TransactionTestCase
from rest_framework.test import APIClient

User = get_user_model()
        
@freeze_time("2025-12-08T11:45:00+07:00")
class CartTest(TransactionTestCase):
    reset_sequences = True  # otomatis reset PK jadi 1
    

    def setUp(self):
        self.client = APIClient()
        call_command("seed_product")
        
        self.user = User.objects.create_user(
            username="test",
            email="test@gmail.com",
            password="test2938484jr",
            phone_number="089384442947"
        )
        EmailAddress.objects.create(
            user=self.user,
            email=self.user.email,
            verified=True,
            primary=True
        )
    
    def handle_login(self):
        login = self.client.post(
            reverse("rest_login"),
            {
                "email": self.user.email,
                "password": "test2938484jr"
            },
            format="json"
        )
        
        self.assertEqual(login.status_code, 200)
        
        token = login.data["access"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        
    @patch("accounts.signals.logger")
    def test_post(self, mock_logger):
        self.handle_login()
        
        res = self.client.post(reverse("add_to_cart", args=[1]), data={})
        
        self.assertEqual(res.status_code, 201)
        
        data = res.data
        self.assertEqual(data["id"], 1)
        self.assertEqual(data["user"], 1)
        self.assertEqual(data["qty"], 1)
        self.assertEqual(data["created_at"], "2025-12-08T11:45:00+07:00")
        self.assertEqual(data["updated_at"], "2025-12-08T11:45:00+07:00")
        
        # cek data bagian product
        self.assertEqual(data["product"]["id"], 1)
        self.assertEqual(data["product"]["name"], "Sample Product 1")
        self.assertEqual(data["product"]["stock"], 50)
        self.assertEqual(data["product"]["created_at"], "2025-12-08T11:45:00+07:00")
        self.assertEqual(data["product"]["updated_at"], "2025-12-08T11:45:00+07:00")
    
        # cek data bagian category
        self.assertEqual(data["product"]["category"]["id"], 1)
        self.assertEqual(data["product"]["category"]["name"], "Default Category")
        self.assertEqual(data["product"]["category"]["desc"], "Sample category")
        self.assertEqual(data["product"]["category"]["created_at"], "2025-12-08T11:45:00+07:00")
        self.assertEqual(data["product"]["category"]["updated_at"], "2025-12-08T11:45:00+07:00")
    
    @patch("accounts.signals.logger")
    def test_post_product_not_found(self, mock_logger):
        self.handle_login()
        res = self.client.post(reverse("add_to_cart", args=[99]), data={})
        self.assertEqual(res.status_code, 404)
        data = res.data
        self.assertEqual(data["detail"], "Product not found")
        
    @patch("accounts.signals.logger")
    def test_get(self, mock_logger):
        self.handle_login()
        res_post = self.client.post(reverse("add_to_cart", args=[1]), data={})
        self.assertEqual(res_post.status_code, 201)
        
        res_get = self.client.get(reverse("cart"))
        self.assertEqual(res_get.status_code, 200)
        
        self.assertEqual(len(res_get.data), 1)
        
        data = res_get.data[0]
        self.assertEqual(data["id"], 1)
        self.assertEqual(data["user"], 1)
        self.assertEqual(data["qty"], 1)
        self.assertEqual(data["created_at"], "2025-12-08T11:45:00+07:00")
        self.assertEqual(data["updated_at"], "2025-12-08T11:45:00+07:00")
        
        # cek data bagian product
        self.assertEqual(data["product"]["id"], 1)
        self.assertEqual(data["product"]["name"], "Sample Product 1")
        self.assertEqual(data["product"]["stock"], 50)
        self.assertEqual(data["product"]["created_at"], "2025-12-08T11:45:00+07:00")
        self.assertEqual(data["product"]["updated_at"], "2025-12-08T11:45:00+07:00")
    
        # cek data bagian category
        self.assertEqual(data["product"]["category"]["id"], 1)
        self.assertEqual(data["product"]["category"]["name"], "Default Category")
        self.assertEqual(data["product"]["category"]["desc"], "Sample category")
        self.assertEqual(data["product"]["category"]["created_at"], "2025-12-08T11:45:00+07:00")
        self.assertEqual(data["product"]["category"]["updated_at"], "2025-12-08T11:45:00+07:00")
        
    
    @patch("accounts.signals.logger")
    def test_patch(self, mock_logger):
        self.handle_login()
        res_post = self.client.post(reverse("add_to_cart", args=[1]), data={})
        self.assertEqual(res_post.status_code, 201)
        
        # test quantity (qty) cart
        self.assertEqual(res_post.data["id"], 1)
        self.assertEqual(res_post.data["qty"], 1)
        
        res_patch = self.client.patch(reverse("cart", args=[1]), data={"qty":3})
        self.assertEqual(res_patch.status_code, 200)
        
        # test quantity (qty) cart
        self.assertEqual(res_patch.data["id"], 1)
        self.assertEqual(res_patch.data["qty"], 3)
        
    @patch("accounts.signals.logger")
    def test_patch_cart_not_found(self, mock_logger):
        self.handle_login()
        res_post = self.client.post(reverse("add_to_cart", args=[1]), data={})
        self.assertEqual(res_post.status_code, 201)
        
        res_patch = self.client.patch(reverse("cart", args=[99]), data={})
        self.assertEqual(res_patch.status_code, 404)
        data = res_patch.data
        self.assertEqual(data["detail"], "Item not found in cart")
        
        
    @patch("accounts.signals.logger")
    def test_patch_qty_nothing_in_body_requests(self, mock_logger):
        self.handle_login()
        res_post = self.client.post(reverse("add_to_cart", args=[1]), data={})
        self.assertEqual(res_post.status_code, 201)
        
        res_patch = self.client.patch(reverse("cart", args=[1]), data={})
        self.assertEqual(res_patch.status_code, 400)
        data = res_patch.data
        self.assertEqual(data["qty"][0], "Field qty is required.")
        
        
    @patch("accounts.signals.logger")
    def test_patch_qty_less_than_one(self, mock_logger):
        self.handle_login()
        res_post = self.client.post(reverse("add_to_cart", args=[1]), data={})
        self.assertEqual(res_post.status_code, 201)
        
        res_patch = self.client.patch(reverse("cart", args=[1]), data={"qty":0})
        self.assertEqual(res_patch.status_code, 400)
        data = res_patch.data
        self.assertEqual(data["qty"][0], "Quantity must be greater than 0.")
        
    @patch("accounts.signals.logger")
    def test_patch_qty_exceed_product_stock(self, mock_logger):
        self.handle_login()
        res_post = self.client.post(reverse("add_to_cart", args=[1]), data={})
        self.assertEqual(res_post.status_code, 201)
        
        res_patch = self.client.patch(reverse("cart", args=[1]), data={"qty":999})
        self.assertEqual(res_patch.status_code, 400)
        data = res_patch.data
        self.assertEqual(data["qty"][0], "Quantity cannot exceed stock 50.")
        
        
        