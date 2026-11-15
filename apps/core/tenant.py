from django.core.exceptions import PermissionDenied
from django.db import models


class TenantQuerySet(models.QuerySet):
    def for_salon(self, salon):
        if salon is None:
            return self.none()
        salon_id = salon.pk if hasattr(salon, "pk") else salon
        if salon_id is None:
            return self.none()
        return self.filter(salon_id=salon_id)


class TenantManager(models.Manager):
    def get_queryset(self):
        return TenantQuerySet(self.model, using=self._db)

    def for_salon(self, salon):
        return self.get_queryset().for_salon(salon)


class TenantModelMixin(models.Model):
    """All business data must reference a salon."""

    salon = models.ForeignKey(
        "salons.Salon",
        on_delete=models.PROTECT,
        related_name="%(app_label)s_%(class)s_set",
    )

    objects = TenantManager()

    class Meta:
        abstract = True

    @classmethod
    def scoped(cls, salon):
        return cls.objects.for_salon(salon)


def require_salon_access(user, salon, min_role=None):
    from apps.salons.models import SalonMembership

    if not user.is_authenticated:
        raise PermissionDenied
    if user.is_superuser:
        return SalonMembership.Role.OWNER
    membership = (
        SalonMembership.objects.filter(user=user, salon=salon, is_active=True)
        .select_related("salon")
        .first()
    )
    if membership is None:
        raise PermissionDenied
    if min_role is not None:
        if membership.role_rank < SalonMembership.role_rank_for(min_role):
            raise PermissionDenied
    return membership.role
