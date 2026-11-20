"""Idempotent follow-up queue based on actual completed visits."""
from django.db import transaction
from django.db.models import Case, IntegerField, Max, Q, Value, When
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.customers.models import Customer
from apps.retention.models import FollowUp
from apps.salons.models import Salon, SalonSettings


def visit_customers(salon):
    return Customer.scoped(salon).filter(is_deleted=False).annotate(
        actual_last_visit=Max("appointments__start_at",filter=Q(appointments__salon=salon,appointments__status=Appointment.Status.COMPLETED)))


def open_queue(salon):
    return FollowUp.scoped(salon).filter(status=FollowUp.Status.OPEN,customer__is_deleted=False,customer__salon=salon).annotate(
        priority_rank=Case(When(priority=FollowUp.Priority.HIGH,then=Value(3)),When(priority=FollowUp.Priority.MEDIUM,then=Value(2)),default=Value(1),output_field=IntegerField())
    ).select_related("customer").order_by("-priority_rank","-days_since_visit","pk")


@transaction.atomic
def sync_follow_up_queue(salon):
    # Serialize sync command / manual refresh for a salon, including legacy adoption.
    Salon.objects.select_for_update(no_key=True).get(pk=salon.pk)
    settings=SalonSettings.objects.filter(salon=salon).first()
    if not settings or not salon.is_active:
        return 0
    now=timezone.now()
    today=timezone.localdate(now)
    low,medium,high=sorted([max(1,settings.retention_days_30),max(1,settings.retention_days_60),max(1,settings.retention_days_90)])
    future=set(Appointment.scoped(salon).filter(start_at__gte=now,status__in=[Appointment.Status.PENDING,Appointment.Status.CONFIRMED,Appointment.Status.CHECKED_IN]).values_list("customer_id",flat=True))
    FollowUp.scoped(salon).filter(customer__is_deleted=True,status__in=[FollowUp.Status.OPEN,FollowUp.Status.SNOOZED]).update(status=FollowUp.Status.DONE,updated_at=now)
    created_count=0
    for customer in visit_customers(salon).iterator(chunk_size=500):
        baseline=customer.actual_last_visit or customer.created_at
        key=baseline.isoformat()
        days=max(0,(today-timezone.localdate(baseline)).days)
        active=FollowUp.scoped(salon).filter(customer=customer,status__in=[FollowUp.Status.OPEN,FollowUp.Status.SNOOZED])
        # A genuine new visit ends the previous automatic cycle.
        active.exclude(cycle_key="").exclude(cycle_key=key).update(status=FollowUp.Status.DONE,updated_at=now)
        if customer.pk in future:
            # Keep history; a booked visit temporarily hides automatic reminders.
            active.filter(cycle_key=key,status=FollowUp.Status.OPEN).update(status=FollowUp.Status.SNOOZED,next_follow_up_at=today,updated_at=now)
            continue
        if days<low:
            continue
        priority=FollowUp.Priority.HIGH if days>=high else FollowUp.Priority.MEDIUM if days>=medium else FollowUp.Priority.LOW
        threshold=high if days>=high else medium if days>=medium else low
        reason=f"{threshold} روز بدون مراجعه" if customer.actual_last_visit else f"{threshold} روز از ثبت مشتری بدون مراجعه"
        row=FollowUp.scoped(salon).select_for_update().filter(customer=customer,cycle_key=key).first()
        if row is None:
            # Preserve old completed follow-up decisions instead of resurrecting them on upgrade.
            row=FollowUp.scoped(salon).select_for_update().filter(customer=customer,cycle_key="",created_at__gte=baseline).order_by("-created_at","-pk").first()
            if row:
                row.cycle_key=key
                row.save(update_fields=["cycle_key","updated_at"])
            else:
                row=FollowUp.objects.create(salon=salon,customer=customer,cycle_key=key,reason=reason,days_since_visit=days,priority=priority)
                created_count+=1
        if row.status==FollowUp.Status.DONE:
            continue
        if row.status==FollowUp.Status.SNOOZED and (row.next_follow_up_at is None or row.next_follow_up_at>today):
            continue
        row.status=FollowUp.Status.OPEN
        row.priority=priority
        row.reason=reason
        row.days_since_visit=days
        row.next_follow_up_at=None
        row.save(update_fields=["status","priority","reason","days_since_visit","next_follow_up_at","updated_at"])
    return created_count
