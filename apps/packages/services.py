from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.packages.models import CustomerPackage, PackageSessionUse


@transaction.atomic
def consume_package_session(customer_package: CustomerPackage, appointment) -> PackageSessionUse:
    from apps.appointments.models import Appointment

    appointment = Appointment.objects.select_for_update().get(pk=appointment.pk)
    customer_package = CustomerPackage.objects.select_for_update().get(pk=customer_package.pk)
    if customer_package.salon_id != appointment.salon_id or customer_package.customer_id != appointment.customer_id:
        raise ValidationError("پکیج متعلق به مشتری یا سالن این نوبت نیست.")
    if appointment.status in (Appointment.Status.CANCELLED, Appointment.Status.NO_SHOW):
        raise ValidationError("برای نوبت لغوشده یا عدم حضور نمی‌توان جلسه مصرف کرد.")
    if customer_package.sessions_remaining <= 0:
        raise ValidationError("جلسات پکیج تمام شده است.")
    if customer_package.expires_at <= timezone.now():
        raise ValidationError("اعتبار پکیج منقضی شده است.")
    from apps.finance.models import InvoiceLine
    if InvoiceLine.objects.filter(appointment=appointment).exists():
        raise ValidationError("برای این نوبت فاکتور صادر شده است.")
    if PackageSessionUse.objects.filter(appointment=appointment).exists():
        raise ValidationError("برای این نوبت قبلاً جلسه پکیج ثبت شده است.")

    customer_package.sessions_used += 1
    customer_package.save(update_fields=["sessions_used", "updated_at"])
    return PackageSessionUse.objects.create(
        salon=customer_package.salon,
        customer_package=customer_package,
        appointment=appointment,
    )
