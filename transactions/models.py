from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum


class CounterpartyType(models.TextChoices):
    BUYER = "BUYER", "مشتري"
    SELLER = "SELLER", "بائع"
    SUPPLIER = "SUPPLIER", "مورد"
    OTHER = "OTHER", "أخرى"


class Counterparty(models.Model):
    farm = models.ForeignKey("core.Farm", on_delete=models.CASCADE, related_name="counterparties", verbose_name="المنشأة")
    name = models.CharField(max_length=150, verbose_name="الاسم")
    party_type = models.CharField(max_length=20, choices=CounterpartyType.choices, default=CounterpartyType.OTHER, verbose_name="نوع الطرف")
    phone = models.CharField(max_length=30, blank=True, verbose_name="رقم الجوال")
    notes = models.TextField(blank=True, verbose_name="ملاحظات")

    class Meta:
        verbose_name = "طرف تعامل"
        verbose_name_plural = "أطراف التعامل"
        constraints = [
            models.UniqueConstraint(fields=["farm", "name", "party_type"], name="uniq_counterparty_per_farm"),
        ]
        indexes = [
            models.Index(fields=["farm", "party_type"]),
            models.Index(fields=["farm", "phone"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_party_type_display()})"


class TransactionType(models.TextChoices):
    SALE = "SALE", "بيع"
    PURCHASE = "PURCHASE", "شراء"
    EXPENSE = "EXPENSE", "مصروف"
    INCOME = "INCOME", "دخل"
    ADJUSTMENT = "ADJUSTMENT", "تسوية"


class TransactionStatus(models.TextChoices):
    DRAFT = "DRAFT", "مسودة"
    POSTED = "POSTED", "مرحل"
    CANCELED = "CANCELED", "ملغي"


class PaymentMode(models.TextChoices):
    PAID = "PAID", "مدفوع"
    CREDIT = "CREDIT", "بالآجل"


class Transaction(models.Model):
    farm = models.ForeignKey("core.Farm", on_delete=models.CASCADE, related_name="transactions", verbose_name="المنشأة")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_transactions", verbose_name="أنشئت بواسطة"
    )

    tx_type = models.CharField(max_length=20, choices=TransactionType.choices, default=TransactionType.EXPENSE, verbose_name="النوع")
    status = models.CharField(max_length=20, choices=TransactionStatus.choices, default=TransactionStatus.DRAFT, verbose_name="الحالة")

    date = models.DateField(verbose_name="التاريخ")
    reference = models.CharField(max_length=80, blank=True, verbose_name="مرجع/فاتورة")
    counterparty = models.ForeignKey("transactions.Counterparty", on_delete=models.SET_NULL, null=True, blank=True, related_name="transactions", verbose_name="طرف التعامل")

    # ✅ منع التكرار (Idempotency)
    idempotency_key = models.CharField(max_length=64, unique=True, null=True, blank=True, verbose_name="مفتاح منع التكرار")

    # ✅ مرتجع بدل تعديل
    is_return = models.BooleanField(default=False, verbose_name="مرتجع")
    original_tx = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="return_txs", verbose_name="مرتجع عن")

    # ✅ الدفع
    payment_mode = models.CharField(max_length=10, choices=PaymentMode.choices, default=PaymentMode.PAID, verbose_name="طريقة الدفع")
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="المبلغ المدفوع")
    amount_due = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="المتبقي (آجل)")

    # ✅ بيانات عميل مباشرة (اختياري)
    customer_name = models.CharField(max_length=150, blank=True, verbose_name="اسم العميل")
    customer_phone = models.CharField(max_length=30, blank=True, verbose_name="رقم الجوال")

    notes = models.TextField(blank=True, verbose_name="ملاحظات")

    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="الإجمالي")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")

    class Meta:
        verbose_name = "معاملة"
        verbose_name_plural = "المعاملات"
        ordering = ["-date", "-created_at"]
        indexes = [
            models.Index(fields=["farm", "date"]),
            models.Index(fields=["farm", "tx_type", "status"]),
            models.Index(fields=["payment_mode"]),
            models.Index(fields=["is_return"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_tx_type_display()} #{self.id} @ {self.date}"

    def recalc_total(self) -> Decimal:
        agg = self.lines.aggregate(s=Sum("amount"))
        total = agg["s"] or Decimal("0.00")
        self.total_amount = total
        return total


class LivestockKind(models.TextChoices):
    SHEEP = "SHEEP", "غنم"
    GOAT = "GOAT", "ماعز"
    HARRI = "HARRI", "طليان (حري)"
    SAWAKNI = "SAWAKNI", "طليان (سواكني)"
    NAIMI = "NAIMI", "طليان (نعيمي)"
    CAMEL = "CAMEL", "إبل"
    COW = "COW", "بقر"


class LivestockClass(models.TextChoices):
    NONE = "NONE", "—"
    JADH = "JADH", "جذع"
    THANI = "THANI", "ثني"


class LineType(models.TextChoices):
    ANIMAL = "ANIMAL", "حيوان"
    SERVICE = "SERVICE", "خدمة"
    ITEM = "ITEM", "صنف"
    OTHER = "OTHER", "أخرى"


class TransactionLine(models.Model):
    transaction = models.ForeignKey("transactions.Transaction", on_delete=models.CASCADE, related_name="lines", verbose_name="المعاملة")

    line_type = models.CharField(max_length=20, choices=LineType.choices, default=LineType.ANIMAL, verbose_name="نوع البند")
    description = models.CharField(max_length=200, blank=True, verbose_name="الوصف")

    livestock_kind = models.CharField(max_length=20, choices=LivestockKind.choices, default=LivestockKind.SHEEP, verbose_name="نوع المواشي")
    livestock_class = models.CharField(max_length=10, choices=LivestockClass.choices, default=LivestockClass.NONE, verbose_name="الصنف")

    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1, verbose_name="الكمية")
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="سعر الوحدة")
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="الإجمالي")

    animal = models.ForeignKey("herd.Animal", on_delete=models.SET_NULL, null=True, blank=True, related_name="transaction_lines", verbose_name="الحيوان")
    group = models.ForeignKey("herd.HerdGroup", on_delete=models.SET_NULL, null=True, blank=True, related_name="transaction_lines", verbose_name="المجموعة")

    class Meta:
        verbose_name = "بند معاملة"
        verbose_name_plural = "بنود المعاملات"
        indexes = [
            models.Index(fields=["transaction"]),
            models.Index(fields=["livestock_kind", "livestock_class"]),
        ]

    def __str__(self) -> str:
        return f"بند #{self.id} -> معاملة #{self.transaction_id}"

    def save(self, *args, **kwargs):
        q = self.quantity or Decimal("0.00")
        p = self.unit_price or Decimal("0.00")
        self.amount = (q * p).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)


class PaymentMethod(models.TextChoices):
    CASH = "CASH", "نقدي"
    TRANSFER = "TRANSFER", "تحويل"
    OTHER = "OTHER", "أخرى"


class Payment(models.Model):
    farm = models.ForeignKey("core.Farm", on_delete=models.CASCADE, related_name="payments", verbose_name="المنشأة")
    transaction = models.ForeignKey("transactions.Transaction", on_delete=models.CASCADE, related_name="payments", verbose_name="المعاملة")
    counterparty = models.ForeignKey("transactions.Counterparty", on_delete=models.SET_NULL, null=True, blank=True, related_name="payments", verbose_name="طرف التعامل")

    date = models.DateField(verbose_name="التاريخ")
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="المبلغ")
    method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH, verbose_name="طريقة السداد")
    notes = models.CharField(max_length=200, blank=True, verbose_name="ملاحظات")

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="أُنشئ بواسطة")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")

    class Meta:
        verbose_name = "سداد"
        verbose_name_plural = "السداد"
        indexes = [
            models.Index(fields=["farm", "date"]),
            models.Index(fields=["transaction"]),
            models.Index(fields=["counterparty"]),
        ]

    def __str__(self) -> str:
        return f"{self.amount} @ {self.date} (Tx {self.transaction_id})"