import secrets
import string

from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel
from apps.core.tenant import TenantModelMixin


def generate_tracking_code() -> str:
    alphabet = string.digits + string.ascii_uppercase
    return "".join(secrets.choice(alphabet) for _ in range(8))


class Appointment(TenantModelMixin, TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار"
        CONFIRMED = "confirmed", "تأیید شده"
        CHECKED_IN = "checked_in", "پذیرش"
        COMPLETED = "completed", "انجام شده"
        CANCELLED = "cancelled", "لغو"
        NO_SHOW = "no_show", "عدم حضور"

    class Source(models.TextChoices):
        INTERNAL = "internal", "داخلی"
        PUBLIC = "public", "رزرو آنلاین"

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="appointments",
    )
    staff = models.ForeignKey(
        "staff.StaffProfile",
        on_delete=models.PROTECT,
        related_name="appointments",
    )
    service = models.ForeignKey(
        "services.Service",
        on_delete=models.PROTECT,
        related_name="appointments",
    )
    start_at = models.DateTimeField(db_index=True)
    end_at = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.INTERNAL)
    price_toman = models.BigIntegerField(default=0)
    notes = models.TextField(blank=True)
    tracking_code = models.CharField(max_length=12, unique=True, db_index=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["salon", "start_at"]),
            models.Index(fields=["salon", "staff", "start_at"]),
            models.Index(fields=["salon", "status", "start_at"]),
        ]
        ordering = ["start_at"]

    def save(self, *args, **kwargs):
        if not self.tracking_code:
            for _ in range(5):
                code = generate_tracking_code()
                if not Appointment.objects.filter(tracking_code=code).exists():
                    self.tracking_code = code
                    break
        super().save(*args, **kwargs)

    def cancel(self):
        self.status = self.Status.CANCELLED
        self.cancelled_at = timezone.now()
        self.save(update_fields=["status", "cancelled_at", "updated_at"])


class PublicBookingPhoneVerification(TimeStampedModel):
    session_key = models.CharField(max_length=40, db_index=True)
    salon = models.ForeignKey(
        "salons.Salon",
        on_delete=models.CASCADE,
        related_name="public_booking_phone_verifications",
    )
    phone = models.CharField(max_length=16, db_index=True)
    otp_challenge = models.ForeignKey(
        "accounts.OTPChallenge",
        on_delete=models.PROTECT,
        related_name="public_booking_verifications",
    )
    expires_at = models.DateTimeField(db_index=True)
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["session_key", "salon", "-created_at"]),
            models.Index(fields=["salon", "phone", "-created_at"]),
        ]

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_consumed(self):
        return self.consumed_at is not None
