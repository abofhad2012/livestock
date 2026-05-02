from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase

from rest_framework.authtoken.models import Token

from accounts.models import FarmMembership, Profile, UserRole
from core.models import Farm


class AuthApiTests(TestCase):
    register_url = "/api/auth/register/"
    login_url = "/api/auth/login/"
    logout_url = "/api/auth/logout/"
    me_url = "/api/auth/me/"

    password = "S3cure-Pass-2026!"

    def _create_linked_user(self, username="owner"):
        User = get_user_model()
        user = User.objects.create_user(username=username, password=self.password)
        farm = Farm.objects.create(name=f"{username} Farm", is_active=True)

        Profile.objects.create(
            user=user,
            farm=farm,
            full_name=f"{username} Name",
            phone="0500000000",
            role=UserRole.OWNER,
            is_active=True,
        )

        FarmMembership.objects.create(
            user=user,
            farm=farm,
            role=UserRole.OWNER,
            is_active=True,
        )

        return user, farm

    def test_register_creates_user_farm_profile_membership_group_and_token(self):
        response = self.client.post(
            self.register_url,
            data={
                "username": "mobile_owner",
                "password": self.password,
                "full_name": "Mobile Owner",
                "phone": "0500000000",
                "farm_name": "Mobile Farm",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)

        data = response.json()
        self.assertTrue(data["ok"])
        self.assertIn("token", data)
        self.assertEqual(data["user"]["username"], "mobile_owner")
        self.assertEqual(data["farm"]["name"], "Mobile Farm")

        User = get_user_model()
        user = User.objects.get(username="mobile_owner")
        farm = Farm.objects.get(name="Mobile Farm")

        self.assertTrue(Token.objects.filter(user=user, key=data["token"]).exists())
        self.assertEqual(Profile.objects.get(user=user).farm, farm)
        self.assertTrue(
            FarmMembership.objects.filter(
                user=user,
                farm=farm,
                role=UserRole.OWNER,
                is_active=True,
            ).exists()
        )
        self.assertTrue(Group.objects.filter(name="Operators", user=user).exists())
        self.assertTrue(user.has_perm("transactions.view_transaction"))

    def test_register_rejects_duplicate_username_case_insensitive(self):
        self._create_linked_user(username="DuplicateOwner")

        response = self.client.post(
            self.register_url,
            data={
                "username": "duplicateowner",
                "password": self.password,
                "farm_name": "Duplicate Farm",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])

    def test_login_returns_token_and_farm(self):
        user, farm = self._create_linked_user(username="login_owner")

        response = self.client.post(
            self.login_url,
            data={"username": "login_owner", "password": self.password},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["user"]["id"], user.id)
        self.assertEqual(data["farm"]["id"], farm.id)
        self.assertTrue(Token.objects.filter(user=user, key=data["token"]).exists())

    def test_invalid_login_returns_400(self):
        self._create_linked_user(username="bad_login_owner")

        response = self.client.post(
            self.login_url,
            data={"username": "bad_login_owner", "password": "wrong-password"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])

    def test_me_returns_current_user_and_farm(self):
        user, farm = self._create_linked_user(username="me_owner")
        token = Token.objects.create(user=user)

        response = self.client.get(
            self.me_url,
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["user"]["id"], user.id)
        self.assertEqual(data["farm"]["id"], farm.id)

    def test_me_rejects_missing_token(self):
        response = self.client.get(self.me_url)

        self.assertEqual(response.status_code, 401)

    def test_logout_deletes_token(self):
        user, _farm = self._create_linked_user(username="logout_owner")
        token = Token.objects.create(user=user)

        response = self.client.post(
            self.logout_url,
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertFalse(Token.objects.filter(key=token.key).exists())
