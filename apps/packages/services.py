from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.packages.models import CustomerPackage, PackageSessionUse


@transaction.atomic
def consume_package_session(customer_package: CustomerPackage, appointment) -> PackageSessionUse:
    customer_package = CustomerPackage.objects.select_for_update().get(pk=customer_package.pk)
    if customer_package.sessions_remaining <= 0:
        raise ValidationError("جلسات پکیج تمام شده است.")
    if customer_package.expires_at < timezone.now():
        raise ValidationError("اعتبار پکیج منقضی شده است.")
    if PackageSessionUse.objects.filter(appointment=appointment).exists():
        raise ValidationError("برای این نوبت قبلاً جلسه پکیج ثبت شده است.")

    customer_package.sessions_used += 1
    customer_package.save(update_fields=["sessions_used", "updated_at"])
    return PackageSessionUse.objects.create(
        salon=customer_package.salon,
        customer_package=customer_package,
        appointment=appointment,
    )
