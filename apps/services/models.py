from django.db import models

from apps.core.models import SoftDeleteModel, TimeStampedModel
from apps.core.tenant import TenantModelMixin


class ServiceCategory(TenantModelMixin, SoftDeleteModel, TimeStampedModel):
    name = models.CharField(max_length=80)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["salon", "name"],
                condition=models.Q(is_deleted=False),
                name="unique_service_category_per_salon",
            ),
        ]

    def __str__(self):
        return self.name


class Service(TenantModelMixin, SoftDeleteModel, TimeStampedModel):
    category = models.ForeignKey(
        ServiceCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="services",
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveIntegerField(default=30)
    price_toman = models.BigIntegerField(default=0)
    image = models.ImageField(upload_to="services/", blank=True, null=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "name"]
        indexes = [models.Index(fields=["salon", "is_active", "is_public"])]

    def __str__(self):
        return self.name
