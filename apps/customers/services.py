from django.db import transaction
from django.db.models import Sum

from apps.customers.models import Customer, CustomerActivity


@transaction.atomic
def log_activity(
    *,
    salon,
    customer: Customer,
    activity_type: str,
    title: str,
    actor=None,
    description: str = "",
    entity_type: str = "",
    entity_id: str = "",
    metadata=None,
):
    return CustomerActivity.objects.create(
        salon=salon,
        customer=customer,
        activity_type=activity_type,
        title=title,
        description=description,
        actor=actor,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata=metadata or {},
    )


def refresh_customer_stats(customer: Customer):
    from apps.appointments.models import Appointment
    from apps.finance.models import Payment

    completed = Appointment.scoped(customer.salon).filter(
        customer=customer,
        status=Appointment.Status.COMPLETED,
    )
    customer.total_visits = completed.count()
    first = completed.order_by("start_at").values_list("start_at", flat=True).first()
    last = completed.order_by("-start_at").values_list("start_at", flat=True).first()
    customer.first_visit_at = first
    customer.last_visit_at = last
    paid = (
        Payment.scoped(customer.salon)
        .filter(customer=customer, status__in=[Payment.Status.PAID, Payment.Status.PARTIAL], paid_amount_toman__gt=0)
        .aggregate(total=Sum("paid_amount_toman"))
    )
    from apps.finance.models import Refund
    refunded = Refund.scoped(customer.salon).filter(payment__customer=customer).aggregate(total=Sum("amount_toman"))["total"] or 0
    customer.total_spent_toman = max(0, (paid["total"] or 0) - refunded)
    customer.save(
        update_fields=[
            "total_visits",
            "first_visit_at",
            "last_visit_at",
            "total_spent_toman",
            "updated_at",
        ]
    )
