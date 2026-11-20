"""Appointment checkout: immutable invoice plus existing receipt rows in one transaction."""
import hashlib
import json
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.appointments.models import Appointment
from apps.audit.models import AuditLog
from apps.customers.models import Customer
from apps.customers.services import refresh_customer_stats
from apps.finance.models import Invoice, InvoiceLine, Payment
from apps.packages.models import PackageSessionUse


MAX_MONEY = 2**63 - 1


def appointment_amounts(appointment):
    valid = [p for p in appointment.payments.all() if p.salon_id == appointment.salon_id
             and p.customer_id == appointment.customer_id and p.status != Payment.Status.REFUNDED]
    gross = max(0, int(appointment.price_toman))
    from apps.finance.ledger import payment_refunded
    paid = sum(max(0, int(p.paid_amount_toman) - payment_refunded(p)) for p in valid)
    discount = sum(max(0, int(p.discount_toman)) for p in valid)
    return gross, paid, discount, max(0, gross - paid - discount)


@transaction.atomic
def issue_invoice(*, salon, customer_id, appointment_ids, request_key, discount, amounts, actor, voucher_id=None):
    try:
        key = UUID(str(request_key))
        ids = sorted({int(pk) for pk in appointment_ids})
        customer_id = int(customer_id)
        if not 0 < customer_id <= MAX_MONEY or not 0 < len(ids) <= 50 or any(not 0 < pk <= MAX_MONEY for pk in ids):
            raise ValueError
        if voucher_id is not None:
            voucher_id=int(voucher_id)
            if not 0<voucher_id<=MAX_MONEY:raise ValueError
        if not isinstance(discount, int) or not 0 <= discount <= MAX_MONEY:
            raise ValueError
        if set(amounts) != set(Payment.Method.values) or any(
            not isinstance(v, int) or not 0 <= v <= MAX_MONEY for v in amounts.values()
        ):
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("اطلاعات فاکتور معتبر نیست.") from None
    payload=[customer_id,ids,discount,amounts]
    if voucher_id is not None:payload.append(voucher_id)
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def existing():
        invoice = Invoice.scoped(salon).filter(request_key=key).first()
        if invoice and invoice.request_digest != digest:
            raise ValidationError("این درخواست قبلاً با اطلاعات متفاوت ثبت شده است.")
        return invoice

    if invoice := existing():
        return invoice

    # Same row lock as the legacy single-appointment receipt service. Stable order
    # prevents concurrent checkouts on overlapping appointment sets from deadlocking.
    appointments = list(Appointment.scoped(salon).select_for_update().filter(
        pk__in=ids, customer_id=customer_id).order_by("pk"))
    if invoice := existing():
        return invoice
    if len(appointments) != len(ids) or any(a.status != Appointment.Status.COMPLETED for a in appointments):
        raise ValidationError("فقط خدمات انجام‌شده همین مشتری قابل انتخاب هستند.")
    if InvoiceLine.objects.filter(appointment_id__in=ids).exists():
        raise ValidationError("برای یکی از این خدمات قبلاً فاکتور صادر شده است.")
    if PackageSessionUse.objects.filter(appointment_id__in=ids).exists():
        raise ValidationError("خدمات پوشش داده‌شده با پکیج در این صندوق دوباره فروخته نمی‌شوند.")
    customer = Customer.scoped(salon).filter(pk=customer_id, is_deleted=False).first()
    if customer is None:
        raise ValidationError("مشتری معتبر نیست.")
    snapshots = []
    for appointment in appointments:
        gross, paid_before, discount_before, owed = appointment_amounts(appointment)
        if paid_before + discount_before > gross:
            raise ValidationError("مانده یکی از خدمات نیازمند بررسی مالی است.")
        snapshots.append((appointment, gross, paid_before, discount_before, owed))
    gross_total = sum(s[1] for s in snapshots)
    paid_before_total = sum(s[2] for s in snapshots)
    discount_before_total = sum(s[3] for s in snapshots)
    owed_total = sum(s[4] for s in snapshots)
    voucher=None
    if voucher_id is not None:
        from apps.loyalty.benefits import lock_voucher
        voucher=lock_voucher(salon=salon,customer=customer,voucher_id=voucher_id)
        discount+=voucher.amount_toman
    received = sum(amounts.values())
    if gross_total > MAX_MONEY or discount + received > owed_total:
        raise ValidationError("تخفیف و دریافتی نمی‌تواند بیش از مانده خدمات باشد.")
    invoice, created = Invoice.objects.get_or_create(salon=salon, request_key=key, defaults={
        "customer": customer, "customer_name": customer.full_name[:200], "request_digest": digest,
        "gross_toman": gross_total, "prior_paid_toman": paid_before_total,
        "prior_discount_toman": discount_before_total, "discount_toman": discount,
        "received_toman": received, "balance_at_issue_toman": owed_total-discount-received,
    })
    if not created:
        if invoice.request_digest != digest:
            raise ValidationError("این درخواست قبلاً با اطلاعات متفاوت ثبت شده است.")
        return invoice
    if voucher:
        voucher.invoice=invoice
        voucher.save(update_fields=["invoice","updated_at"])
        AuditLog.objects.create(salon=salon,actor=actor,action=AuditLog.Action.UPDATE,entity_type="loyalty_voucher",entity_id=str(voucher.pk),message="مصرف اعتبار در صندوق",metadata={"invoice_id":invoice.pk,"amount_toman":voucher.amount_toman})
    discount_left = discount
    method_left = dict(amounts)
    for appointment, gross, paid_before, discount_before, owed in snapshots:
        line_discount = min(owed, discount_left)
        discount_left -= line_discount
        remaining = owed - line_discount
        allocations = []
        for method in Payment.Method.values:
            amount = min(remaining, method_left[method])
            if amount:
                allocations.append((method, amount))
                remaining -= amount
                method_left[method] -= amount
        if line_discount and not allocations:
            allocations.append((Payment.Method.CASH, 0))
        line_received = sum(amount for _, amount in allocations)
        InvoiceLine.objects.create(salon=salon, invoice=invoice, appointment=appointment,
            service_name=appointment.service.name, staff_name=appointment.staff.full_display_name[:200],
            gross_toman=gross, prior_paid_toman=paid_before, prior_discount_toman=discount_before,
            discount_toman=line_discount, received_toman=line_received, balance_at_issue_toman=remaining)
        previous_balance = owed
        for index, (method, amount) in enumerate(allocations):
            applied_discount = line_discount if index == 0 else 0
            after = previous_balance - applied_discount - amount
            status = Payment.Status.PAID if after == 0 else Payment.Status.PARTIAL if amount else Payment.Status.PENDING
            payment = Payment.objects.create(salon=salon, customer=customer, appointment=appointment,
                invoice=invoice, total_amount_toman=previous_balance, discount_toman=applied_discount,
                paid_amount_toman=amount, method=method, status=status, notes="ثبت از صندوق یکپارچه")
            from apps.loyalty.automation import award_payment
            award_payment(payment)
            AuditLog.objects.create(salon=salon, actor=actor, action=AuditLog.Action.CREATE,
                entity_type="payment", entity_id=str(payment.pk), message="دریافت صندوق",
                metadata={"invoice_id": invoice.pk, "paid_amount_toman": amount})
            previous_balance = after
    if discount_left or any(method_left.values()):
        raise ValidationError("تقسیم مبالغ فاکتور کامل نشد.")
    refresh_customer_stats(customer)
    AuditLog.objects.create(salon=salon, actor=actor, action=AuditLog.Action.CREATE,
        entity_type="invoice", entity_id=str(invoice.pk), message="صدور فاکتور خدمات",
        metadata={"appointment_ids": ids, "received_toman": received, "discount_toman": discount})
    return invoice
