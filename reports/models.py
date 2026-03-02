from django.conf import settings
from django.db import models


class ReportType(models.TextChoices):
    SUMMARY = "SUMMARY", "ملخص عام"
    PROFIT_LOSS = "PROFIT_LOSS", "أرباح وخسائر"
    INVENTORY = "INVENTORY", "المخزون"
    HEALTH = "HEALTH", "الصحة"
    CUSTOM = "CUSTOM", "مخصص"


class SavedReport(models.Model):
    farm = models.ForeignKey("core.Farm", on_delete=models.CASCADE, related_name="saved_reports", verbose_name="المنشأة")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="أنشئ بواسطة")

    name = models.CharField(max_length=150, verbose_name="اسم التقرير")
    report_type = models.CharField(max_length=30, choices=ReportType.choices, default=ReportType.SUMMARY, verbose_name="نوع التقرير")
    params = models.JSONField(default=dict, blank=True, verbose_name="إعدادات التقرير")
    is_favorite = models.BooleanField(default=False, verbose_name="مفضل")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")

    class Meta:
        verbose_name = "تقرير محفوظ"
        verbose_name_plural = "التقارير المحفوظة"
        constraints = [
            models.UniqueConstraint(fields=["farm", "name"], name="uniq_saved_report_name_per_farm"),
        ]
        indexes = [
            models.Index(fields=["farm", "report_type"]),
            models.Index(fields=["is_favorite"]),
        ]

    def __str__(self) -> str:
        return self.name


class ReportSnapshot(models.Model):
    farm = models.ForeignKey("core.Farm", on_delete=models.CASCADE, related_name="report_snapshots", verbose_name="المنشأة")
    saved_report = models.ForeignKey(
        "reports.SavedReport",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="snapshots",
        verbose_name="التقرير",
    )

    period_start = models.DateField(null=True, blank=True, verbose_name="بداية الفترة")
    period_end = models.DateField(null=True, blank=True, verbose_name="نهاية الفترة")

    data = models.JSONField(default=dict, blank=True, verbose_name="بيانات التقرير")
    generated_at = models.DateTimeField(auto_now_add=True, verbose_name="وقت التوليد")

    class Meta:
        verbose_name = "لقطة تقرير"
        verbose_name_plural = "لقطات التقارير"
        ordering = ["-generated_at"]
        indexes = [
            models.Index(fields=["farm", "generated_at"]),
        ]

    def __str__(self) -> str:
        return f"لقطة #{self.id} - {self.generated_at.date()}"