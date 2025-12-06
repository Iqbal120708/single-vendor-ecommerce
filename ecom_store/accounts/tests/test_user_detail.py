from rest_framework.test import APITestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from allauth.account.models import EmailAddress
from unittest.mock import patch

User = get_user_model()


class UserDetailTest(APITestCase):
    #reset_sequences = True
    
    def setUp(self):
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
        
    @patch("accounts.signals.logger")
    def test_success(self, mock_logger):
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
        
        response_user = self.client.get(reverse("rest_user_details"))
        
        self.assertEqual(response_user.status_code, 200)
        
        self.assertEqual(response_user.data["id"], 1)
        self.assertEqual(response_user.data["first_name"], "")
        self.assertEqual(response_user.data["last_name"], "")
        self.assertEqual(response_user.data["username"], "test")
        self.assertEqual(response_user.data["email"], "test@gmail.com")
        self.assertEqual(response_user.data["phone_number"], "+6289384442947")