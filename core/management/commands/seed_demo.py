from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Seed demo data for Livestock project (farm, herd, transactions, reports)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Remove previously seeded demo farm and related objects.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        # Imports داخل handle لتفادي مشاكل الاستيراد أثناء المايغريشن
        from core.models import Farm
        from accounts.models import Profile, FarmMembership, UserRole
        from herd.models import HerdGroup, Animal, Species, Sex, AnimalStatus
        from transactions.models import (
            Counterparty,
            CounterpartyType,
            Transaction,
            TransactionType,
            TransactionStatus,
            TransactionLine,
            LineType,
        )
        from reports.models import SavedReport, ReportType, ReportSnapshot

        demo_farm_name = "مزرعة الرياض (تجريبي)"

        # RESET
        if options.get("reset"):
            farm = Farm.objects.filter(name=demo_farm_name).first()
            if not farm:
                self.stdout.write(self.style.WARNING("No demo farm found to reset."))
                return

            # فك الارتباطات التي تمنع حذف Farm (Profile.farm = PROTECT)
            Profile.objects.filter(farm=farm).update(farm=None)
            FarmMembership.objects.filter(farm=farm).delete()

            # حذف التقارير/المعاملات/المواشي تتبع farm (غالبًا CASCADE)
            ReportSnapshot.objects.filter(farm=farm).delete()
            SavedReport.objects.filter(farm=farm).delete()

            TransactionLine.objects.filter(transaction__farm=farm).delete()
            Transaction.objects.filter(farm=farm).delete()
            Counterparty.objects.filter(farm=farm).delete()

            Animal.objects.filter(farm=farm).delete()
            HerdGroup.objects.filter(farm=farm).delete()

            farm.delete()
            self.stdout.write(self.style.SUCCESS("✅ Demo data reset done."))
            return

        # USER
        User = get_user_model()
        user = User.objects.order_by("id").first()
        if not user:
            self.stdout.write(self.style.ERROR("No users found. Create a superuser first."))
            return

        # FARM
        farm, _ = Farm.objects.get_or_create(
            name=demo_farm_name,
            defaults={
                "city": "الرياض",
                "timezone": "Asia/Riyadh",
                "phone": "0500000000",
                "address": "الرياض",
                "is_active": True,
            },
        )

        # PROFILE + MEMBERSHIP (اختياري لكن مفيد)
        Profile.objects.get_or_create(
            user=user,
            defaults={
                "farm": farm,
                "full_name": "المدير التجريبي",
                "phone": "0500000000",
                "role": UserRole.ADMIN,
                "is_active": True,
            },
        )
        FarmMembership.objects.get_or_create(
            user=user,
            farm=farm,
            defaults={"role": UserRole.ADMIN, "is_active": True},
        )

        # HERD GROUPS
        g_sheep, _ = HerdGroup.objects.get_or_create(
            farm=farm,
            name="غنم - القطيع الرئيسي",
            defaults={"species": Species.SHEEP, "notes": "مجموعة تجريبية"},
        )
        g_goat, _ = HerdGroup.objects.get_or_create(
            farm=farm,
            name="ماعز - القطيع الفرعي",
            defaults={"species": Species.GOAT, "notes": "مجموعة تجريبية"},
        )

        # ANIMALS (بعض الحيوانات مع tags)
        def create_animal(tag: str, group: HerdGroup, sex=Sex.UNKNOWN):
            kwargs = dict(
                farm=farm,
                group=group,
                tag=tag,
                species=group.species,
                breed="",
                sex=sex,
                status=AnimalStatus.ACTIVE,
                notes="",
            )
            # لو عندك حقل age_class في موديل Animal، نعبيه تلقائيًا
            try:
                Animal._meta.get_field("age_class")
                kwargs["age_class"] = "JADH" if tag.endswith(("1", "2", "3", "4", "5")) else "THANI"
            except Exception:
                pass

            Animal.objects.get_or_create(farm=farm, tag=tag, defaults=kwargs)

        for i in range(1, 9):
            create_animal(f"SHEEP-{i:03d}", g_sheep, Sex.MALE if i % 2 == 0 else Sex.FEMALE)
        for i in range(1, 5):
            create_animal(f"GOAT-{i:03d}", g_goat, Sex.FEMALE)

        # COUNTERPARTIES
        supplier, _ = Counterparty.objects.get_or_create(
            farm=farm,
            name="مورد تجريبي",
            party_type=CounterpartyType.SUPPLIER,
            defaults={"phone": "0551111111", "notes": ""},
        )
        buyer, _ = Counterparty.objects.get_or_create(
            farm=farm,
            name="إبراهيم",
            party_type=CounterpartyType.BUYER,
            defaults={"phone": "0552222222", "notes": "عميل تجريبي"},
        )

        today = timezone.now().date()

        # PURCHASE TRANSACTION
        tx_buy, _ = Transaction.objects.get_or_create(
            farm=farm,
            tx_type=TransactionType.PURCHASE,
            date=today,
            reference="PO-001",
            defaults={
                "status": TransactionStatus.POSTED,
                "created_by": user,
                "counterparty": supplier,
                "notes": "شراء تجريبي",
                "total_amount": Decimal("0.00"),
            },
        )
        TransactionLine.objects.get_or_create(
            transaction=tx_buy,
            line_type=LineType.OTHER,
            description="شراء غنم (جملة)",
            defaults={
                "quantity": Decimal("10"),
                "unit_price": Decimal("900"),
                "animal": None,
                "group": g_sheep,
            },
        )
        tx_buy.recalc_total()
        tx_buy.save(update_fields=["total_amount"])

        # SALE TRANSACTION
        tx_sale, _ = Transaction.objects.get_or_create(
            farm=farm,
            tx_type=TransactionType.SALE,
            date=today,
            reference="SO-001",
            defaults={
                "status": TransactionStatus.POSTED,
                "created_by": user,
                "counterparty": buyer,
                "notes": "بيع تجريبي - مدفوع/آجل يُسجل في الملاحظات مؤقتًا",
                "total_amount": Decimal("0.00"),
            },
        )
        TransactionLine.objects.get_or_create(
            transaction=tx_sale,
            line_type=LineType.OTHER,
            description="بيع غنم",
            defaults={
                "quantity": Decimal("5"),
                "unit_price": Decimal("1000"),
                "animal": None,
                "group": g_sheep,
            },
        )
        tx_sale.recalc_total()
        tx_sale.save(update_fields=["total_amount"])

        # REPORTS
        sr, _ = SavedReport.objects.get_or_create(
            farm=farm,
            name="ملخص اليوم",
            defaults={
                "created_by": user,
                "report_type": ReportType.SUMMARY,
                "params": {"date": str(today)},
                "is_favorite": True,
            },
        )
        ReportSnapshot.objects.get_or_create(
            farm=farm,
            saved_report=sr,
            period_start=today,
            period_end=today,
            defaults={"data": {"note": "لقطة تجريبية", "date": str(today)}},
        )

        self.stdout.write(self.style.SUCCESS("✅ Demo data created successfully."))
        self.stdout.write(f"Farm: {farm.name}")