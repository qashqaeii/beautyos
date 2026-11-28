"""Capture allowlisted product milestones after successful database commits.

No customer names, phones, invoice amounts, or salon-private content are sent.
"""
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.appointments.models import Appointment
from apps.customers.models import Customer
from apps.finance.models import Invoice
from apps.staff.models import StaffProfile
from apps.platform_admin.activity_metrics import record_activity
from apps.platform_admin.models import PlatformActivityEvent


def _emit_on_commit(instance, kind, key_prefix):
    salon_id = instance.salon_id
    object_id = instance.pk

    def emit():
        from apps.salons.models import Salon
        salon = Salon.objects.filter(pk=salon_id).first()
        if salon is not None:
            record_activity(
                salon=salon, kind=kind,
                dedupe_key=f"{key_prefix}:{object_id}",
            )

    transaction.on_commit(emit)


@receiver(post_save, sender=Appointment, dispatch_uid="platform_appointment_created_v1")
def appointment_created_event(sender, instance, created, **kwargs):
    if created:
        _emit_on_commit(instance, PlatformActivityEvent.Kind.APPOINTMENT_CREATED, "appointment-created")


@receiver(post_save, sender=Customer, dispatch_uid="platform_customer_created_v1")
def customer_created_event(sender, instance, created, **kwargs):
    if created:
        _emit_on_commit(instance, PlatformActivityEvent.Kind.CUSTOMER_CREATED, "customer-created")


@receiver(post_save, sender=StaffProfile, dispatch_uid="platform_staff_created_v1")
def staff_created_event(sender, instance, created, **kwargs):
    if created:
        _emit_on_commit(instance, PlatformActivityEvent.Kind.STAFF_CREATED, "staff-created")


@receiver(post_save, sender=Invoice, dispatch_uid="platform_invoice_created_v1")
def invoice_created_event(sender, instance, created, **kwargs):
    if created:
        _emit_on_commit(instance, PlatformActivityEvent.Kind.INVOICE_CREATED, "invoice-created")
