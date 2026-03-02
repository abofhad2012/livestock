from django.conf import settings
from django.db import models


class UserRole(models.TextChoices):
    OWNER = "OWNER", "مالك"
    ADMIN = "ADMIN", "مدير"
    STAFF = "STAFF", "موظف"
    VIEWER = "VIEWER", "مشاهد"


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name="المستخدم",
    )
    farm = models.ForeignKey(
        "core.Farm",
        on_delete=models.PROTECT,
        related_name="profiles",
        null=True,
        blank=True,
        verbose_name="المنشأة",
    )
    full_name = models.CharField(max_length=150, blank=True, verbose_name="الاسم الكامل")
    phone = models.CharField(max_length=30, blank=True, verbose_name="رقم الجوال")
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.STAFF, verbose_name="الدور")
    is_active = models.BooleanField(default=True, verbose_name="نشط")

    class Meta:
        verbose_name = "ملف مستخدم"
        verbose_name_plural = "ملفات المستخدمين"
        indexes = [
            models.Index(fields=["farm", "role"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self) -> str:
        return self.full_name or getattr(self.user, "username", "user")


class FarmMembership(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name="المستخدم",
    )
    farm = models.ForeignKey(
        "core.Farm",
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name="المنشأة",
    )
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.STAFF, verbose_name="الدور")
    joined_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الانضمام")
    is_active = models.BooleanField(default=True, verbose_name="نشط")

    class Meta:
        verbose_name = "عضوية منشأة"
        verbose_name_plural = "عضويات المنشآت"
        constraints = [
            models.UniqueConstraint(fields=["user", "farm"], name="uniq_user_farm_membership"),
        ]
        indexes = [
            models.Index(fields=["farm", "role", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} @ {self.farm} ({self.get_role_display()})"