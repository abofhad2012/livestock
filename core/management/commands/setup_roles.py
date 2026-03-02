from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create default roles/groups for livestock project."

    def handle(self, *args, **options):
        operator, _ = Group.objects.get_or_create(name="مشغل")
        reports_viewer, _ = Group.objects.get_or_create(name="مشاهدة التقارير")

        def add_perms(group: Group, app_label: str, model: str, codenames: list[str]):
            ct = ContentType.objects.get(app_label=app_label, model=model)
            for codename in codenames:
                perm = Permission.objects.get(content_type=ct, codename=codename)
                group.permissions.add(perm)

        # مشغل: إضافة/تعديل/عرض معاملات + سداد
        add_perms(operator, "transactions", "transaction", ["add_transaction", "change_transaction", "view_transaction"])
        add_perms(operator, "transactions", "transactionline", ["add_transactionline", "change_transactionline", "view_transactionline"])
        add_perms(operator, "transactions", "counterparty", ["add_counterparty", "change_counterparty", "view_counterparty"])
        add_perms(operator, "transactions", "payment", ["add_payment", "view_payment"])

        # مشاهدة التقارير: عرض فقط
        add_perms(reports_viewer, "transactions", "transaction", ["view_transaction"])
        add_perms(reports_viewer, "transactions", "transactionline", ["view_transactionline"])
        add_perms(reports_viewer, "transactions", "counterparty", ["view_counterparty"])
        add_perms(reports_viewer, "transactions", "payment", ["view_payment"])

        self.stdout.write(self.style.SUCCESS("✅ Groups updated: مشغل, مشاهدة التقارير"))