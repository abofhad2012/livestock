from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")

    class Meta:
        abstract = True


class Farm(TimeStampedModel):
    name = models.CharField(max_length=150, verbose_name="اسم المنشأة")
    city = models.CharField(max_length=80, default="الرياض", verbose_name="المدينة")
    timezone = models.CharField(max_length=64, default="Asia/Riyadh", verbose_name="المنطقة الزمنية")
    phone = models.CharField(max_length=30, blank=True, verbose_name="رقم الهاتف")
    address = models.TextField(blank=True, verbose_name="العنوان")
    is_active = models.BooleanField(default=True, verbose_name="نشط")

    class Meta:
        verbose_name = "منشأة"
        verbose_name_plural = "المنشآت"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self) -> str:
        return self.name