from django.db import models


class Species(models.TextChoices):
    SHEEP = "SHEEP", "غنم"
    GOAT = "GOAT", "ماعز"
    CAMEL = "CAMEL", "إبل"
    COW = "COW", "بقر"
    OTHER = "OTHER", "أخرى"


class Sex(models.TextChoices):
    MALE = "M", "ذكر"
    FEMALE = "F", "أنثى"
    UNKNOWN = "U", "غير محدد"


class AnimalStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "نشط"
    SOLD = "SOLD", "مباع"
    DEAD = "DEAD", "نافِق"
    LOST = "LOST", "مفقود"


class HerdGroup(models.Model):
    farm = models.ForeignKey("core.Farm", on_delete=models.CASCADE, related_name="herd_groups", verbose_name="المنشأة")
    name = models.CharField(max_length=120, verbose_name="اسم المجموعة")
    species = models.CharField(max_length=20, choices=Species.choices, default=Species.SHEEP, verbose_name="النوع")
    notes = models.TextField(blank=True, verbose_name="ملاحظات")

    class Meta:
        verbose_name = "مجموعة"
        verbose_name_plural = "المجموعات"
        constraints = [
            models.UniqueConstraint(fields=["farm", "name"], name="uniq_group_name_per_farm"),
        ]
        indexes = [
            models.Index(fields=["farm", "species"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_species_display()})"


class Animal(models.Model):
    farm = models.ForeignKey("core.Farm", on_delete=models.CASCADE, related_name="animals", verbose_name="المنشأة")
    group = models.ForeignKey(
        "herd.HerdGroup",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="animals",
        verbose_name="المجموعة",
    )

    tag = models.CharField(max_length=60, verbose_name="الوسم/الترقيم")
    species = models.CharField(max_length=20, choices=Species.choices, default=Species.SHEEP, verbose_name="النوع")
    breed = models.CharField(max_length=80, blank=True, verbose_name="السلالة")
    sex = models.CharField(max_length=1, choices=Sex.choices, default=Sex.UNKNOWN, verbose_name="الجنس")

    birth_date = models.DateField(null=True, blank=True, verbose_name="تاريخ الميلاد")
    purchase_date = models.DateField(null=True, blank=True, verbose_name="تاريخ الشراء")

    status = models.CharField(max_length=20, choices=AnimalStatus.choices, default=AnimalStatus.ACTIVE, verbose_name="الحالة")
    notes = models.TextField(blank=True, verbose_name="ملاحظات")

    class Meta:
        verbose_name = "حيوان"
        verbose_name_plural = "الحيوانات"
        constraints = [
            models.UniqueConstraint(fields=["farm", "tag"], name="uniq_tag_per_farm"),
        ]
        indexes = [
            models.Index(fields=["farm", "status"]),
            models.Index(fields=["farm", "species"]),
        ]

    def __str__(self) -> str:
        return f"{self.tag} - {self.get_species_display()}"


class WeightRecord(models.Model):
    animal = models.ForeignKey("herd.Animal", on_delete=models.CASCADE, related_name="weights", verbose_name="الحيوان")
    date = models.DateField(verbose_name="التاريخ")
    weight_kg = models.DecimalField(max_digits=7, decimal_places=2, verbose_name="الوزن (كجم)")
    notes = models.CharField(max_length=200, blank=True, verbose_name="ملاحظات")

    class Meta:
        verbose_name = "قياس وزن"
        verbose_name_plural = "قياسات الوزن"
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["animal", "date"]),
        ]

    def __str__(self) -> str:
        return f"{self.animal} @ {self.date}: {self.weight_kg}kg"


class HealthRecordType(models.TextChoices):
    VACCINE = "VACCINE", "تلقيح"
    TREATMENT = "TREATMENT", "علاج"
    CHECKUP = "CHECKUP", "فحص"
    OTHER = "OTHER", "أخرى"


class HealthRecord(models.Model):
    animal = models.ForeignKey("herd.Animal", on_delete=models.CASCADE, related_name="health_records", verbose_name="الحيوان")
    record_type = models.CharField(max_length=20, choices=HealthRecordType.choices, default=HealthRecordType.CHECKUP, verbose_name="نوع السجل")
    date = models.DateField(verbose_name="التاريخ")
    description = models.TextField(blank=True, verbose_name="الوصف")
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="التكلفة")

    class Meta:
        verbose_name = "سجل صحي"
        verbose_name_plural = "السجلات الصحية"
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["animal", "date"]),
            models.Index(fields=["record_type", "date"]),
        ]

    def __str__(self) -> str:
        return f"{self.animal} - {self.get_record_type_display()} @ {self.date}"


class ReproductionOutcome(models.TextChoices):
    PREGNANT = "PREGNANT", "حمل"
    BIRTH = "BIRTH", "ولادة"
    ABORTION = "ABORTION", "إجهاض"
    UNKNOWN = "UNKNOWN", "غير محدد"


class ReproductionRecord(models.Model):
    female = models.ForeignKey("herd.Animal", on_delete=models.CASCADE, related_name="repro_female_records", verbose_name="الأنثى")
    male = models.ForeignKey(
        "herd.Animal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="repro_male_records",
        verbose_name="الذكر",
    )
    date = models.DateField(verbose_name="التاريخ")
    outcome = models.CharField(max_length=20, choices=ReproductionOutcome.choices, default=ReproductionOutcome.UNKNOWN, verbose_name="النتيجة")
    kids_count = models.PositiveIntegerField(default=0, verbose_name="عدد المواليد")
    notes = models.TextField(blank=True, verbose_name="ملاحظات")

    class Meta:
        verbose_name = "سجل تكاثر"
        verbose_name_plural = "سجلات التكاثر"
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["female", "date"]),
            models.Index(fields=["outcome", "date"]),
        ]

    def __str__(self) -> str:
        return f"{self.female} @ {self.date} ({self.get_outcome_display()})"