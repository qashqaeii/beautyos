from django.db import models

from apps.core.models import SoftDeleteModel, TimeStampedModel
from apps.core.tenant import TenantModelMixin
from apps.salons.models import SalonMembership


class StaffProfile(TenantModelMixin, SoftDeleteModel, TimeStampedModel):
    membership = models.OneToOneField(
        SalonMembership,
        on_delete=models.CASCADE,
        related_name="staff_profile",
    )
    display_name = models.CharField(max_length=120, blank=True)
    title = models.CharField(max_length=80, blank=True)
    bio = models.TextField(blank=True)
    avatar = models.ImageField(upload_to="staff/avatars/", blank=True, null=True)
    is_bookable = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    calendar_color = models.CharField(
        max_length=7,
        blank=True,
        default="",
        help_text="رنگ اختصاصی نوبت‌ها در تقویم ماهانه",
    )
    services = models.ManyToManyField("services.Service", blank=True, related_name="staff_members")

    class Meta:
        indexes = [models.Index(fields=["salon", "is_active", "is_bookable"])]

    def __str__(self):
        return self.display_name or str(self.membership.user)

    @property
    def user(self):
        return self.membership.user

    @property
    def full_display_name(self) -> str:
        if self.display_name:
            return self.display_name.strip()
        user = self.membership.user
        return (getattr(user, "full_name", None) or str(user)).strip()

    @property
    def initials(self) -> str:
        name = self.full_display_name
        if not name:
            return "؟"
        parts = name.split()
        if len(parts) >= 2:
            return f"{parts[0][0]}{parts[-1][0]}"
        if len(name) >= 2:
            return name[:2]
        return name[0]


class StaffWorkHours(TenantModelMixin, TimeStampedModel):
    class Weekday(models.IntegerChoices):
        SAT = 0, "شنبه"
        SUN = 1, "یکشنبه"
        MON = 2, "دوشنبه"
        TUE = 3, "سه‌شنبه"
        WED = 4, "چهارشنبه"
        THU = 5, "پنجشنبه"
        FRI = 6, "جمعه"

    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name="work_hours")
    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_closed = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["staff", "weekday"], name="unique_staff_weekday_hours"),
        ]


class StaffTimeOff(TenantModelMixin, TimeStampedModel):
    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name="time_off")
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.CharField(max_length=200, blank=True)

    class Meta:
        indexes = [models.Index(fields=["staff", "start_date", "end_date"])]
