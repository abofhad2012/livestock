from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone

from rest_framework.authtoken.models import Token

from accounts.models import FarmMembership, Profile, UserRole
from core.models import Farm
from transactions.models import (
    LineType,
    LivestockClass,
    LivestockKind,
    PaymentMode,
    Transaction,
    TransactionLine,
    TransactionStatus,
    TransactionType,
)


class StockApiTests(TestCase):
    stock_url = "/api/stock/"

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        cls.farm_a = Farm.objects.create(name="Farm A", is_active=True)
        cls.farm_b = Farm.objects.create(name="Farm B", is_active=True)

        cls.user_a = User.objects.create_user(username="stock_user_a", password="pass12345")
        cls.user_b = User.objects.create_user(username="stock_user_b", password="pass12345")
        cls.user_without_farm = User.objects.create_user(username="stock_no_farm", password="pass12345")
        cls.user_without_perm = User.objects.create_user(username="stock_no_perm", password="pass12345")

        cls._link_user_to_farm(cls.user_a, cls.farm_a)
        cls._link_user_to_farm(cls.user_b, cls.farm_b)
        cls._link_user_to_farm(cls.user_without_perm, cls.farm_a)

        content_type = ContentType.objects.get_for_model(Transaction)
        cls.view_transaction_permission = Permission.objects.get(
            content_type=content_type,
            codename="view_transaction",
        )

        cls.user_a.user_permissions.add(cls.view_transaction_permission)
        cls.user_b.user_permissions.add(cls.view_transaction_permission)
        cls.user_without_farm.user_permissions.add(cls.view_transaction_permission)

        cls._create_tx_line(
            farm=cls.farm_a,
            user=cls.user_a,
            tx_type=TransactionType.PURCHASE,
            kind=LivestockKind.SHEEP,
            livestock_class=LivestockClass.NONE,
            quantity=Decimal("10.00"),
        )
        cls._create_tx_line(
            farm=cls.farm_a,
            user=cls.user_a,
            tx_type=TransactionType.SALE,
            kind=LivestockKind.SHEEP,
            livestock_class=LivestockClass.NONE,
            quantity=Decimal("3.00"),
        )

        cls._create_tx_line(
            farm=cls.farm_b,
            user=cls.user_b,
            tx_type=TransactionType.PURCHASE,
            kind=LivestockKind.SHEEP,
            livestock_class=LivestockClass.NONE,
            quantity=Decimal("99.00"),
        )

    @staticmethod
    def _link_user_to_farm(user, farm):
        Profile.objects.create(
            user=user,
            farm=farm,
            full_name=user.username,
            role=UserRole.OWNER,
            is_active=True,
        )
        FarmMembership.objects.create(
            user=user,
            farm=farm,
            role=UserRole.OWNER,
            is_active=True,
        )

    @staticmethod
    def _create_tx_line(*, farm, user, tx_type, kind, livestock_class, quantity):
        tx = Transaction.objects.create(
            farm=farm,
            created_by=user,
            tx_type=tx_type,
            status=TransactionStatus.POSTED,
            date=timezone.localdate(),
            payment_mode=PaymentMode.PAID,
            amount_paid=Decimal("0.00"),
            amount_due=Decimal("0.00"),
            total_amount=Decimal("0.00"),
        )

        return TransactionLine.objects.create(
            transaction=tx,
            line_type=LineType.ANIMAL,
            livestock_kind=kind,
            livestock_class=livestock_class,
            quantity=quantity,
            unit_price=Decimal("100.00"),
        )

    @staticmethod
    def _auth_headers(user):
        token = Token.objects.create(user=user)
        return {"HTTP_AUTHORIZATION": f"Token {token.key}"}

    def test_stock_requires_token(self):
        response = self.client.get(self.stock_url)

        self.assertEqual(response.status_code, 401)

    def test_stock_requires_permission(self):
        response = self.client.get(
            self.stock_url,
            **self._auth_headers(self.user_without_perm),
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.json()["ok"])

    def test_user_without_farm_does_not_fallback_to_first_farm(self):
        response = self.client.get(
            self.stock_url,
            **self._auth_headers(self.user_without_farm),
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data["ok"])
        self.assertEqual(data["error"], "farm is required")

    def test_stock_returns_only_current_users_farm_quantities(self):
        response = self.client.get(
            self.stock_url,
            **self._auth_headers(self.user_a),
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["farm"]["id"], self.farm_a.id)

        self.assertEqual(len(data["items"]), 1)
        item = data["items"][0]

        self.assertEqual(item["kind"], LivestockKind.SHEEP)
        self.assertEqual(item["livestock_class"], LivestockClass.NONE)
        self.assertEqual(item["quantity"], "7.00")

        self.assertEqual(len(data["by_kind"]), 1)
        self.assertEqual(data["by_kind"][0]["kind"], LivestockKind.SHEEP)
        self.assertEqual(data["by_kind"][0]["total"], "7.00")
