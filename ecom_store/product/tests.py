from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse
from freezegun import freeze_time
from rest_framework.test import APIClient
from django.test import TransactionTestCase

User = get_user_model()


@freeze_time("2025-12-08T11:45:00+07:00")
class ProductTest(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.client = APIClient()
        
        call_command("seed_product")

        self.user = User.objects.create_user(
            username="test",
            email="test@gmail.com",
            password="test2938484jr",
            phone_number="089384442947",
        )
        EmailAddress.objects.create(
            user=self.user, email=self.user.email, verified=True, primary=True
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
    def test_category(self, mock_logger):
        self.handle_login()
        res = self.client.get(reverse("category"))

        self.assertEqual(res.status_code, 200)

        self.assertEqual(len(res.data), 1)

        data = res.data[0]
        self.assertEqual(data["id"], 1)
        self.assertEqual(data["name"], "Default Category")
        self.assertEqual(data["desc"], "Sample category")
        self.assertEqual(data["created_at"], "2025-12-08T11:45:00+07:00")
        self.assertEqual(data["updated_at"], "2025-12-08T11:45:00+07:00")

    @patch("accounts.signals.logger")
    def test_product(self, mock_logger):
        self.handle_login()
        res = self.client.get(reverse("product"))

        self.assertEqual(res.status_code, 200)

        self.assertEqual(len(res.data), 10)

        for i, data in enumerate(res.data):
            # skip price dan weight karena nilai random
            self.assertEqual(data["id"], i + 1)
            self.assertEqual(data["name"], f"Sample Product {i+1}")
            self.assertEqual(data["stock"], 50)

            # cek data bagian category
            self.assertEqual(data["category"]["id"], 1)
            self.assertEqual(data["category"]["name"], "Default Category")
            self.assertEqual(data["category"]["desc"], "Sample category")
            self.assertEqual(
                data["category"]["created_at"], "2025-12-08T11:45:00+07:00"
            )
            self.assertEqual(
                data["category"]["updated_at"], "2025-12-08T11:45:00+07:00"
            )

            # self.assertEqual(data["category_id"], 1)
            self.assertEqual(data["created_at"], "2025-12-08T11:45:00+07:00")
            self.assertEqual(data["updated_at"], "2025-12-08T11:45:00+07:00")

    @patch("accounts.signals.logger")
    def test_product_detail(self, mock_logger):
        self.handle_login()
        res = self.client.get(reverse("product_detail", args=[1]))

        self.assertEqual(res.status_code, 200)

        data = res.data
        # skip price dan weight karena nilai random
        self.assertEqual(data["id"], 1)
        self.assertEqual(data["name"], f"Sample Product 1")
        self.assertEqual(data["stock"], 50)
        self.assertEqual(data["created_at"], "2025-12-08T11:45:00+07:00")
        self.assertEqual(data["updated_at"], "2025-12-08T11:45:00+07:00")

        # cek data bagian category
        self.assertEqual(data["category"]["id"], 1)
        self.assertEqual(data["category"]["name"], "Default Category")
        self.assertEqual(data["category"]["desc"], "Sample category")
        self.assertEqual(data["category"]["created_at"], "2025-12-08T11:45:00+07:00")
        self.assertEqual(data["category"]["updated_at"], "2025-12-08T11:45:00+07:00")

    @patch("accounts.signals.logger")
    def test_product_detail_not_found(self, mock_logger):
        self.handle_login()
        res = self.client.get(reverse("product_detail", args=[99]))

        self.assertEqual(res.status_code, 404)

        data = res.data

        self.assertEqual(data["detail"], "Product not found")
