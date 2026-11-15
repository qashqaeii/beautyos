from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.appointments.models import Appointment
from apps.commissions.services import recognize_commission_for_appointment


@receiver(post_save, sender=Appointment)
def commission_on_appointment_complete(sender, instance, **kwargs):
    """Fallback for legacy creates; lifecycle service is the primary path."""
    if instance.status == Appointment.Status.COMPLETED:
        recognize_commission_for_appointment(instance)