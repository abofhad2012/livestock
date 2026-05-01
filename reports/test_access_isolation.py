from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.utils import timezone

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


class CrossFarmIsolationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        # Ù…Ø²Ø§Ø±Ø¹
        cls.farm_a = Farm.objects.create(name="Ù…Ø²Ø±Ø¹Ø© A", city="Ø§Ù„Ø±ÙŠØ§Ø¶", is_active=True)
        cls.farm_b = Farm.objects.create(name="Ù…Ø²Ø±Ø¹Ø© B", city="Ø¬Ø¯Ø©", is_active=True)

        # Ù…Ø³ØªØ®Ø¯Ù…ÙˆÙ†
        cls.user_a = User.objects.create_user(username="user_a", password="pass12345")
        cls.user_b = User.objects.create_user(username="user_b", password="pass12345")
        cls.user_unlinked = User.objects.create_user(username="user_unlinked", password="pass12345")

        # Ø±Ø¨Ø· Ø§Ù„Ù…Ø³ØªØ®Ø¯Ù…ÙŠÙ† Ø¨Ù…Ø²Ø§Ø±Ø¹Ù‡Ù…
        cls._link_user_to_farm(cls.user_a, cls.farm_a)
        cls._link_user_to_farm(cls.user_b, cls.farm_b)

        # ØµÙ„Ø§Ø­ÙŠØ§Øª Ø§Ù„Ù‚Ø±Ø§Ø¡Ø©/Ø§Ù„ØªØ¹Ø¯ÙŠÙ„ Ø§Ù„Ù„Ø§Ø²Ù…Ø©
        view_perm = Permission.objects.get(
            codename="view_transaction",
            content_type__app_label="transactions",
        )
        change_perm = Permission.objects.get(
            codename="change_transaction",
            content_type__app_label="transactions",
        )

        for u in [cls.user_a, cls.user_b, cls.user_unlinked]:
            u.user_permissions.add(view_perm)

        for u in [cls.user_a, cls.user_b]:
            u.user_permissions.add(change_perm)

        # Ù…Ø¹Ø§Ù…Ù„Ø§Øª Ù…Ù†ÙØµÙ„Ø© Ù„ÙƒÙ„ Ù…Ø²Ø±Ø¹Ø©
        cls.tx_a = cls._make_sale_tx(cls.farm_a, cls.user_a, ref="SO-TEST-A")
        cls.tx_b = cls._make_sale_tx(cls.farm_b, cls.user_b, ref="SO-TEST-B")

    @classmethod
    def _link_user_to_farm(cls, user, farm):
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

    @classmethod
    def _make_sale_tx(cls, farm, user, ref):
        today = timezone.localdate()

        tx = Transaction.objects.create(
            farm=farm,
            created_by=user,
            tx_type=TransactionType.SALE,
            status=TransactionStatus.POSTED,
            date=today,
            reference=ref,
            idempotency_key=f"idem-{ref}",
            is_return=False,
            payment_mode=PaymentMode.PAID,
            amount_paid=Decimal("1000.00"),
            amount_due=Decimal("0.00"),
            total_amount=Decimal("1000.00"),
            customer_name="Ø¹Ù…ÙŠÙ„ Ø§Ø®ØªØ¨Ø§Ø±",
            customer_phone="0500000000",
        )

        TransactionLine.objects.create(
            transaction=tx,
            line_type=LineType.ANIMAL,
            livestock_kind=LivestockKind.NAIMI,
            livestock_class=LivestockClass.JADH,
            quantity=Decimal("1"),
            unit_price=Decimal("1000.00"),
            description="Ø¹Ù…Ù„ÙŠØ© Ø§Ø®ØªØ¨Ø§Ø±",
        )

        return tx

    def test_user_can_open_own_transaction_preview(self):
        self.client.force_login(self.user_a)
        response = self.client.get(f"/reports/tx/{self.tx_a.id}/")
        self.assertEqual(response.status_code, 200)

    def test_user_cannot_open_other_farm_transaction_preview(self):
        self.client.force_login(self.user_a)
        response = self.client.get(f"/reports/tx/{self.tx_b.id}/")
        self.assertEqual(response.status_code, 404)

    def test_user_cannot_open_other_farm_transaction_pdf(self):
        self.client.force_login(self.user_a)
        response = self.client.get(f"/reports/tx/{self.tx_b.id}/pdf/")
        self.assertEqual(response.status_code, 404)

    def test_user_cannot_cancel_other_farm_transaction(self):
        self.client.force_login(self.user_a)
        response = self.client.post(f"/transactions/api/tx/{self.tx_b.id}/cancel/")
        self.assertEqual(response.status_code, 404)

        self.tx_b.refresh_from_db()
        self.assertEqual(self.tx_b.status, TransactionStatus.POSTED)

    def test_user_without_farm_gets_no_farm_error_from_stock_api(self):
        self.client.force_login(self.user_unlinked)
        response = self.client.get("/transactions/api/stock/")

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data["ok"])
        self.assertIn("Farm", data.get("error", ""))
