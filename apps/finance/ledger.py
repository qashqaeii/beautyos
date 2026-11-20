"""Audited refund events and explicit account reconciliation."""
from datetime import date
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.audit.models import AuditLog
from apps.commissions.models import CommissionSettlement
from apps.expenses.models import Expense
from apps.finance.models import AccountMovement, FinancialAccount, Payment, Refund, SalonDebtPayment
from apps.packages.models import CustomerPackage

MAX_MONEY = 2**63 - 1


def amount_sum(qs, field="amount_toman"):
    return int(qs.aggregate(total=Sum(field))["total"] or 0)


def payment_refunded(payment):
    return sum(int(row.amount_toman) for row in payment.refunds.all() if row.salon_id==payment.salon_id)


def refund_total(salon, start, end):
    return amount_sum(Refund.scoped(salon).filter(created_at__gte=start, created_at__lt=end))


def _audit(salon, actor, obj, entity, message, meta):
    AuditLog.objects.create(salon=salon, actor=actor, action=AuditLog.Action.CREATE,
        entity_type=entity, entity_id=str(obj.pk), message=message, metadata=meta)


def _key(value):
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("شناسه درخواست معتبر نیست.") from None


def _positive(amount):
    if not isinstance(amount, int) or not 0 < amount <= MAX_MONEY:
        raise ValidationError("مبلغ معتبر نیست.")


@transaction.atomic
def refund_payment(*, salon, payment_id, amount, reason, request_key, actor):
    from apps.customers.services import refresh_customer_stats

    key = _key(request_key)
    _positive(amount)
    reason = (reason or "").strip()
    if not reason or len(reason) > 255:
        raise ValidationError("علت استرداد را وارد کنید.")
    original = Payment.scoped(salon).filter(pk=payment_id).first()
    if original is None:
        raise ValidationError("پرداخت یافت نشد.")
    # Lock in the same order as appointment payment and checkout.
    if original.appointment_id:
        Appointment.scoped(salon).select_for_update().get(pk=original.appointment_id)
    payment = Payment.scoped(salon).select_for_update().get(pk=payment_id)
    def check(row):
        if (row.payment_id, row.amount_toman, row.reason) != (payment.pk, amount, reason):
            raise ValidationError("درخواست قبلاً با اطلاعات متفاوت ثبت شده است.")
        return row
    previous = Refund.scoped(salon).filter(request_key=key).first()
    if previous:
        return check(previous)
    if payment.status == Payment.Status.REFUNDED or amount > payment.paid_amount_toman - payment_refunded(payment):
        raise ValidationError("مبلغ استرداد بیش از دریافتی قابل برگشت است.")
    # Product returns require a stock reversal, not a generic receipt refund.
    if hasattr(payment, "product_sale"):
        raise ValidationError("استرداد محصول باید از مسیر برگشت کالا انجام شود.")
    row, created = Refund.objects.get_or_create(salon=salon, request_key=key, defaults={
        "payment":payment,"amount_toman":amount,"reason":reason})
    if not created:
        return check(row)
    refresh_customer_stats(payment.customer)
    _audit(salon, actor, row, "refund", "ثبت استرداد", {"payment_id":payment.pk,"amount_toman":amount})
    return row


def account_balance(account):
    moves=AccountMovement.scoped(account.salon)
    return int(account.opening_toman) + amount_sum(moves.filter(to_account=account)) - amount_sum(moves.filter(from_account=account))


def source_event(salon, kind, pk):
    """Return amount, date, direction and receipt method, always from the actual source."""
    models = {"payment":Payment, "refund":Refund, "expense":Expense, "commission":CommissionSettlement,
        "debt":SalonDebtPayment, "package":CustomerPackage}
    if kind=="staff_period":
        from apps.finance.models import StaffPeriodPayment
        row=StaffPeriodPayment.scoped(salon).filter(pk=pk).first()
        if not row: raise ValidationError("گردش متخصص یافت نشد.")
        return row.amount_toman,timezone.localdate(row.created_at),row.kind=="rent",None
    model=models.get(kind)
    if model is None:
        raise ValidationError("نوع گردش معتبر نیست.")
    row=model.scoped(salon).filter(pk=pk).first()
    if not row:
        raise ValidationError("گردش مالی یافت نشد.")
    if kind == "payment":
        if row.status == Payment.Status.REFUNDED:
            raise ValidationError("رسید قدیمی باطل شده است.")
        return row.paid_amount_toman, timezone.localdate(row.created_at), True, row.method
    if kind == "refund":
        return row.amount_toman, timezone.localdate(row.created_at), False, row.payment.method
    if kind == "expense":
        return row.amount_toman, row.expense_date, False, None
    if kind == "commission":
        return row.amount_toman, timezone.localdate(row.settled_at), False, None
    if kind == "package":
        return row.price_paid_toman, timezone.localdate(row.purchased_at), True, None
    return row.amount_toman, timezone.localdate(row.created_at), False, None


@transaction.atomic
def post_movement(*, salon, kind, source_id=None, from_id=None, to_id=None, amount=None, request_key, note="", actor):
    """Transfers use one row for both sides; source posting is once per event."""
    key = _key(request_key)
    note = (note or "").strip()
    if len(note) > 255:
        raise ValidationError("توضیح بیش از حد طولانی است.")
    day = timezone.localdate()
    if kind == "transfer":
        if not from_id or not to_id or from_id == to_id:
            raise ValidationError("دو حساب متفاوت انتخاب کنید.")
        source_id = None
    elif kind in ("payment","refund","expense","commission","debt","package","staff_period"):
        amount, day, inbound, method = source_event(salon, kind, source_id)
        if (inbound and (from_id or not to_id)) or (not inbound and (to_id or not from_id)):
            raise ValidationError("جهت گردش با سند مطابقت ندارد.")
    elif kind in ("other_in","other_out"):
        source_id = None
        if not note or (kind == "other_in" and (from_id or not to_id)) or (kind == "other_out" and (to_id or not from_id)):
            raise ValidationError("حساب و علت ورود یا خروج وجه را مشخص کنید.")
    else:
        raise ValidationError("نوع گردش معتبر نیست.")
    _positive(amount)
    if day > timezone.localdate():
        raise ValidationError("گردش آینده قابل ثبت نیست.")
    ids={pk for pk in (from_id,to_id) if pk is not None}
    accounts={r.pk:r for r in FinancialAccount.scoped(salon).select_for_update().filter(pk__in=ids).order_by("pk")}
    if len(accounts)!=len(ids) or not ids or any(day<a.opening_day for a in accounts.values()):
        raise ValidationError("حساب یا تاریخ افتتاح معتبر نیست.")
    if kind in ("payment","refund") and method:
        account=accounts[to_id or from_id]
        if (method=="cash") != (account.kind=="cash"):
            raise ValidationError("نوع حساب با روش پرداخت مطابقت ندارد.")
    fields={"from_account_id":from_id,"to_account_id":to_id,"source_kind":kind,"source_id":source_id,
        "amount_toman":amount,"day":day,"note":note}
    def check(row):
        if any(getattr(row,k)!=v for k,v in fields.items()):
            raise ValidationError("درخواست قبلاً با اطلاعات متفاوت ثبت شده است.")
        return row
    previous=AccountMovement.scoped(salon).filter(request_key=key).first()
    if previous:
        return check(previous)
    if source_id and AccountMovement.scoped(salon).filter(source_kind=kind,source_id=source_id).exists():
        raise ValidationError("این سند قبلاً به حساب تخصیص داده شده است.")
    if kind=="transfer" and account_balance(accounts[from_id])<amount:
        raise ValidationError("موجودی ثبت‌شده حساب مبدا کافی نیست.")
    from django.db import IntegrityError
    try:
        with transaction.atomic():
            row,created=AccountMovement.objects.get_or_create(salon=salon,request_key=key,defaults=fields)
    except IntegrityError:
        raise ValidationError("این گردش قبلاً ثبت شده است.") from None
    if not created:
        return check(row)
    _audit(salon,actor,row,"account_movement","ثبت گردش حساب",{"kind":kind,"amount_toman":amount})
    return row
