from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    ACCOUNT_EMAIL_VERIFICATION="mandatory",
)
class RegistrationTest(APITestCase):
    def test_success(self):
        url = reverse("rest_register")
        data = {
            "username": "user",
            "email": "user@mail.com",
            "password1": "Tes12345!",
            "password2": "Tes12345!",
            "phone_number": "+628123456789",
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertTrue(User.objects.filter(email="user@mail.com").exists())
        self.assertFalse(EmailAddress.objects.get(email="user@mail.com").verified)

    def test_phonenumber_nothing(self):
        url = reverse("rest_register")
        data = {
            "username": "user",
            "email": "user@mail.com",
            "password1": "Tes12345!",
            "password2": "Tes12345!",
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["phone_number"][0].code, "required")

    def test_phonenumber_invalid(self):
        url = reverse("rest_register")
        data = {
            "username": "user",
            "email": "user@mail.com",
            "password1": "Tes12345!",
            "password2": "Tes12345!",
            "phone_number": "20384399",
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["phone_number"][0].code, "invalid")
