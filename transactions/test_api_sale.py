import json
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
    Payment,
    PaymentMode,
    Transaction,
    TransactionLine,
    TransactionStatus,
    TransactionType,
)


class SaleApiTests(TestCase):
    sale_url = "/api/sale/"
    stock_url = "/api/stock/"

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        cls.farm_a = Farm.objects.create(name="Sale Farm A", is_active=True)
        cls.farm_b = Farm.objects.create(name="Sale Farm B", is_active=True)

        cls.user_a = User.objects.create_user(username="sale_user_a", password="pass12345")
        cls.user_b = User.objects.create_user(username="sale_user_b", password="pass12345")
        cls.user_without_farm = User.objects.create_user(username="sale_no_farm", password="pass12345")
        cls.user_without_perm = User.objects.create_user(username="sale_no_perm", password="pass12345")

        cls._link_user_to_farm(cls.user_a, cls.farm_a)
        cls._link_user_to_farm(cls.user_b, cls.farm_b)
        cls._link_user_to_farm(cls.user_without_perm, cls.farm_a)

        content_type = ContentType.objects.get_for_model(Transaction)
        cls.add_transaction_permission = Permission.objects.get(
            content_type=content_type,
            codename="add_transaction",
        )
        cls.view_transaction_permission = Permission.objects.get(
            content_type=content_type,
            codename="view_transaction",
        )

        cls.user_a.user_permissions.add(
            cls.add_transaction_permission,
            cls.view_transaction_permission,
        )
        cls.user_b.user_permissions.add(
            cls.add_transaction_permission,
            cls.view_transaction_permission,
        )
        cls.user_without_farm.user_permissions.add(
            cls.add_transaction_permission,
            cls.view_transaction_permission,
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
    def _auth_headers(user):
        token, _ = Token.objects.get_or_create(user=user)
        return {"HTTP_AUTHORIZATION": f"Token {token.key}"}

    @staticmethod
    def _payload(**overrides):
        payload = {
            "kind": LivestockKind.SHEEP,
            "livestock_class": LivestockClass.NONE,
            "quantity": "4.00",
            "unit_price": "300.00",
        }
        payload.update(overrides)
        return payload

    def _post_sale(self, user, payload=None):
        return self.client.post(
            self.sale_url,
            data=json.dumps(payload or self._payload()),
            content_type="application/json",
            **self._auth_headers(user),
        )

    @staticmethod
    def _create_purchase_stock(*, farm, user, quantity, kind=LivestockKind.SHEEP, livestock_class=LivestockClass.NONE):
        tx = Transaction.objects.create(
            farm=farm,
            created_by=user,
            tx_type=TransactionType.PURCHASE,
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
            quantity=Decimal(str(quantity)),
            unit_price=Decimal("100.00"),
        )

    def test_sale_requires_token(self):
        response = self.client.post(
            self.sale_url,
            data=json.dumps(self._payload()),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)

    def test_sale_requires_permission(self):
        self._create_purchase_stock(farm=self.farm_a, user=self.user_a, quantity="10.00")

        response = self._post_sale(self.user_without_perm)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.json()["ok"])

    def test_user_without_farm_does_not_fallback_to_first_farm(self):
        self._create_purchase_stock(farm=self.farm_a, user=self.user_a, quantity="10.00")

        response = self._post_sale(self.user_without_farm)

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data["ok"])
        self.assertEqual(data["error"], "farm is required")

        self.assertFalse(
            Transaction.objects.filter(created_by=self.user_without_farm).exists()
        )

    def test_sale_rejects_insufficient_stock(self):
        response = self._post_sale(self.user_a)

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data["ok"])
        self.assertEqual(data["error"], "insufficient stock")
        self.assertEqual(data["available"], "0.00")

    def test_sale_creates_paid_posted_sale_and_reduces_stock(self):
        self._create_purchase_stock(farm=self.farm_a, user=self.user_a, quantity="10.00")

        response = self._post_sale(self.user_a)

        self.assertEqual(response.status_code, 201)

        data = response.json()
        self.assertTrue(data["ok"])
        self.assertFalse(data["idempotent"])

        tx = Transaction.objects.get(pk=data["transaction"]["id"])
        self.assertEqual(tx.farm, self.farm_a)
        self.assertEqual(tx.created_by, self.user_a)
        self.assertEqual(tx.tx_type, TransactionType.SALE)
        self.assertEqual(tx.status, TransactionStatus.POSTED)
        self.assertEqual(tx.payment_mode, PaymentMode.PAID)
        self.assertEqual(tx.total_amount, Decimal("1200.00"))
        self.assertEqual(tx.amount_paid, Decimal("1200.00"))
        self.assertEqual(tx.amount_due, Decimal("0.00"))

        line = TransactionLine.objects.get(transaction=tx)
        self.assertEqual(line.line_type, LineType.ANIMAL)
        self.assertEqual(line.livestock_kind, LivestockKind.SHEEP)
        self.assertEqual(line.livestock_class, LivestockClass.NONE)
        self.assertEqual(line.quantity, Decimal("4.00"))
        self.assertEqual(line.unit_price, Decimal("300.00"))
        self.assertEqual(line.amount, Decimal("1200.00"))

        self.assertTrue(Payment.objects.filter(transaction=tx, amount=Decimal("1200.00")).exists())

        stock_response = self.client.get(
            self.stock_url,
            **self._auth_headers(self.user_a),
        )

        self.assertEqual(stock_response.status_code, 200)
        stock_data = stock_response.json()
        self.assertTrue(stock_data["ok"])
        self.assertEqual(stock_data["farm"]["id"], self.farm_a.id)
        self.assertEqual(stock_data["by_kind"][0]["total"], "6.00")

    def test_sale_does_not_use_other_farm_stock(self):
        self._create_purchase_stock(farm=self.farm_a, user=self.user_a, quantity="10.00")

        response = self._post_sale(self.user_b)

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data["ok"])
        self.assertEqual(data["error"], "insufficient stock")
        self.assertEqual(data["available"], "0.00")

        self.assertFalse(
            Transaction.objects.filter(
                farm=self.farm_b,
                tx_type=TransactionType.SALE,
            ).exists()
        )

    def test_sale_idempotency_returns_existing_transaction_and_does_not_double_subtract(self):
        self._create_purchase_stock(farm=self.farm_a, user=self.user_a, quantity="10.00")

        payload = self._payload(idempotency_key="idem-sale-1")

        first_response = self._post_sale(self.user_a, payload)
        second_response = self._post_sale(self.user_a, payload)

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 200)

        first_data = first_response.json()
        second_data = second_response.json()

        self.assertEqual(
            first_data["transaction"]["id"],
            second_data["transaction"]["id"],
        )
        self.assertTrue(second_data["idempotent"])

        self.assertEqual(
            Transaction.objects.filter(
                farm=self.farm_a,
                idempotency_key="idem-sale-1",
                tx_type=TransactionType.SALE,
            ).count(),
            1,
        )

        stock_response = self.client.get(
            self.stock_url,
            **self._auth_headers(self.user_a),
        )

        stock_data = stock_response.json()
        self.assertEqual(stock_data["by_kind"][0]["total"], "6.00")

    def test_sale_rejects_invalid_quantity(self):
        self._create_purchase_stock(farm=self.farm_a, user=self.user_a, quantity="10.00")

        response = self._post_sale(
            self.user_a,
            self._payload(quantity="0"),
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])

    def test_sale_requires_class_for_tlyan_kind(self):
        response = self._post_sale(
            self.user_a,
            self._payload(
                kind=LivestockKind.HARRI,
                livestock_class=LivestockClass.NONE,
            ),
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])
