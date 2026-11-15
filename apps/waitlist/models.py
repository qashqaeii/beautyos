from django.db import models

from apps.core.models import TimeStampedModel
from apps.core.tenant import TenantModelMixin


class WaitlistEntry(TenantModelMixin, TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "فعال"
        BOOKED = "booked", "رزرو شد"
        CLOSED = "closed", "بسته"

    customer = models.ForeignKey("customers.Customer", on_delete=models.PROTECT, related_name="waitlist_entries")
    service = models.ForeignKey("services.Service", on_delete=models.PROTECT, related_name="waitlist_entries")
    preferred_staff = models.ForeignKey(
        "staff.StaffProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="waitlist_entries",
    )
    preferred_date = models.DateField(null=True, blank=True)
    time_note = models.CharField(max_length=120, blank=True)
    priority = models.PositiveSmallIntegerField(default=5)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    appointment = models.ForeignKey(
        "appointments.Appointment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="from_waitlist",
    )

    class Meta:
        indexes = [models.Index(fields=["salon", "status", "-priority", "created_at"])]
