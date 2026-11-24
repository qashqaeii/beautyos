from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel
from apps.core.tenant import TenantModelMixin


class ServicePackage(TenantModelMixin, TimeStampedModel):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    price_toman = models.BigIntegerField()
    session_count = models.PositiveIntegerField()
    validity_days = models.PositiveIntegerField(default=365)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [models.Index(fields=["salon", "is_active"])]


class CustomerPackage(TenantModelMixin, TimeStampedModel):
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="packages",
    )
    package = models.ForeignKey(ServicePackage, on_delete=models.PROTECT, related_name="sales")
    sessions_total = models.PositiveIntegerField()
    sessions_used = models.PositiveIntegerField(default=0)
    purchased_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    price_paid_toman = models.BigIntegerField()

    class Meta:
        indexes = [models.Index(fields=["salon", "customer", "-purchased_at"])]

    @property
    def sessions_remaining(self) -> int:
        return max(self.sessions_total - self.sessions_used, 0)

    def is_valid(self) -> bool:
        return self.sessions_remaining > 0 and self.expires_at >= timezone.now()


class PackageSessionUse(TenantModelMixin, TimeStampedModel):
    customer_package = models.ForeignKey(CustomerPackage, on_delete=models.PROTECT, related_name="uses")
    # Retain the immutable use event for audit when a completed visit is reversed.
    reversed_at = models.DateTimeField(null=True, blank=True)
    appointment = models.OneToOneField(
        "appointments.Appointment",
        on_delete=models.PROTECT,
        related_name="package_use",
    )
