from django.db import models

from apps.core.models import SoftDeleteModel, TimeStampedModel
from apps.core.tenant import TenantModelMixin


class PortfolioItem(TenantModelMixin, SoftDeleteModel, TimeStampedModel):
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="portfolio/")
    category = models.CharField(max_length=80, blank=True)
    service = models.ForeignKey(
        "services.Service",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portfolio_items",
    )
    sort_order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "-created_at"]
