from django.contrib import admin
from django.utils.html import format_html

from .models import Counterparty, Payment, Transaction, TransactionLine, TransactionStatus


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("reference", "tx_type", "date", "total_amount", "payment_mode", "amount_due", "status", "is_return")
    list_filter = ("tx_type", "status", "payment_mode", "is_return")
    search_fields = ("reference", "customer_name", "customer_phone")
    readonly_fields = ()

    actions = ["cancel_selected"]

    @admin.action(description="إلغاء المعاملات المحددة (بدل التعديل)")
    def cancel_selected(self, request, queryset):
        queryset.filter(status=TransactionStatus.POSTED).update(status=TransactionStatus.CANCELED)

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.status == TransactionStatus.POSTED:
            # نجعل كل شيء للقراءة فقط (التعديل ممنوع)
            return [f.name for f in self.model._meta.fields]
        return []

    def has_delete_permission(self, request, obj=None):
        # لا حذف من لوحة التحكم
        return False


@admin.register(TransactionLine)
class TransactionLineAdmin(admin.ModelAdmin):
    list_display = ("transaction", "livestock_kind", "livestock_class", "quantity", "unit_price", "amount")
    list_filter = ("livestock_kind", "livestock_class")
    readonly_fields = [f.name for f in TransactionLine._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Counterparty)
class CounterpartyAdmin(admin.ModelAdmin):
    list_display = ("name", "party_type", "phone", "farm")
    search_fields = ("name", "phone")
    list_filter = ("party_type",)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("date", "amount", "method", "transaction", "counterparty")
    list_filter = ("method", "date")
    search_fields = ("transaction__reference", "counterparty__name", "counterparty__phone")