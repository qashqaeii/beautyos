"""Capture successful appointment creation without reading salon customer data."""
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.appointments.models import Appointment
from apps.platform_admin.activity_metrics import record_activity
from apps.platform_admin.models import PlatformActivityEvent


@receiver(post_save, sender=Appointment, dispatch_uid="platform_appointment_created_v1")
def appointment_created_event(sender, instance, created, **kwargs):
    if not created:
        return
    salon_id = instance.salon_id
    appointment_id = instance.pk

    def emit():
        from apps.salons.models import Salon
        salon = Salon.objects.filter(pk=salon_id).first()
        if salon is not None:
            record_activity(
                salon=salon,
                kind=PlatformActivityEvent.Kind.APPOINTMENT_CREATED,
                dedupe_key=f"appointment-created:{appointment_id}",
            )

    transaction.on_commit(emit)
