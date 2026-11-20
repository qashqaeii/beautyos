from datetime import date

import jdatetime
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.core.utils.dates import jalali_month_bounds, add_jalali_months, _jalali_days_in_month
from apps.dashboard.role_services import day_bounds
from apps.expenses.models import Expense
from apps.finance.ledger import MAX_MONEY, _audit, _key, _positive, amount_sum
from apps.finance.models import StaffAgreement, StaffPeriod, StaffPeriodPayment, RecurringExpense, ExpenseOccurrence
from apps.staff.models import StaffProfile


def agreement_for(salon, staff_id, day):
    return StaffAgreement.scoped(salon).filter(staff_id=staff_id,effective_month__lte=day).order_by("-effective_month").first()


@transaction.atomic
def create_agreement(*,salon,staff_id,month,mode,amount,actor):
    start,_=jalali_month_bounds(month)
    today=timezone.localdate()
    if start<jalali_month_bounds(today)[0] or mode not in ("commission","salary","hybrid","rent"):
        raise ValidationError("قرارداد فقط از ماه جاری یا ماه‌های آینده قابل تعریف است.")
    if not isinstance(amount,int) or not 0<=amount<=MAX_MONEY or (mode=="commission" and amount!=0) or (mode!="commission" and amount==0):
        raise ValidationError("مبلغ ماهانه متناسب با نوع همکاری وارد کنید.")
    staff=StaffProfile.scoped(salon).select_for_update().filter(pk=staff_id,is_deleted=False).first()
    if not staff:
        raise ValidationError("متخصص معتبر نیست.")
    existing=StaffAgreement.scoped(salon).filter(staff=staff,effective_month=start).first()
    if existing:
        if (existing.mode,existing.monthly_toman)==(mode,amount): return existing
        raise ValidationError("قرارداد این ماه ثبت شده است؛ تغییر برای ماه بعد مجاز است.")
    dt,_=day_bounds(start)
    if Appointment.scoped(salon).filter(staff=staff,status=Appointment.Status.COMPLETED,completed_at__gte=dt).exists() or StaffPeriod.scoped(salon).filter(staff=staff,month__gte=start).exists():
        raise ValidationError("برای این دوره سوابق مالی وجود دارد؛ قرارداد را از ماه بعد تنظیم کنید.")
    row=StaffAgreement.objects.create(salon=salon,staff=staff,effective_month=start,mode=mode,monthly_toman=amount)
    _audit(salon,actor,row,"staff_agreement","تعریف مدل همکاری",{"mode":mode,"monthly_toman":amount})
    return row


@transaction.atomic
def open_staff_period(*,salon,staff_id,month,actor):
    month,_=jalali_month_bounds(month)
    if month>timezone.localdate():
        raise ValidationError("دوره آینده هنوز قابل ثبت نیست.")
    staff=StaffProfile.scoped(salon).select_for_update().filter(pk=staff_id).first()
    if not staff: raise ValidationError("متخصص معتبر نیست.")
    agreement=agreement_for(salon,staff_id,month)
    if not agreement or agreement.mode=="commission": raise ValidationError("برای این ماه حقوق یا اجاره تعریف نشده است.")
    row,created=StaffPeriod.objects.get_or_create(salon=salon,staff=staff,month=month,defaults={
        "agreement":agreement,"kind":"rent" if agreement.mode=="rent" else "salary","amount_toman":agreement.monthly_toman})
    if created: _audit(salon,actor,row,"staff_period","ثبت تعهد ماهانه",{"amount_toman":row.amount_toman})
    return row


@transaction.atomic
def pay_staff_period(*,salon,period_id,kind,amount,request_key,note,actor):
    _positive(amount)
    key=_key(request_key)
    note=(note or "").strip()
    if len(note)>255: raise ValidationError("توضیح طولانی است.")
    period=StaffPeriod.scoped(salon).select_for_update().filter(pk=period_id).first()
    if not period or kind not in (("rent",) if period.kind=="rent" else ("advance","settlement")):
        raise ValidationError("نوع پرداخت با قرارداد مطابقت ندارد.")
    def check(row):
        if (row.period_id,row.kind,row.amount_toman,row.note)!=(period.pk,kind,amount,note):
            raise ValidationError("این درخواست قبلاً با اطلاعات دیگری ثبت شده است.")
        return row
    previous=StaffPeriodPayment.scoped(salon).filter(request_key=key).first()
    if previous:return check(previous)
    remaining=period.amount_toman-amount_sum(period.payments.filter(salon=salon))
    if amount>remaining: raise ValidationError("مبلغ بیش از مانده تعهد است.")
    row,created=StaffPeriodPayment.objects.get_or_create(salon=salon,request_key=key,defaults={"period":period,"kind":kind,"amount_toman":amount,"note":note})
    if not created:return check(row)
    _audit(salon,actor,row,"staff_period_payment","پرداخت یا دریافت همکاری",{"kind":kind,"amount_toman":amount})
    return row


@transaction.atomic
def record_recurring_expense(*,salon,schedule_id,expected_due,actor):
    schedule=RecurringExpense.scoped(salon).select_for_update().filter(pk=schedule_id).first()
    if not schedule: raise ValidationError("هزینه دوره‌ای یافت نشد.")
    previous=ExpenseOccurrence.scoped(salon).filter(schedule=schedule,due_day=expected_due).first()
    if previous:return previous
    if not schedule.is_active or schedule.next_due!=expected_due or expected_due>timezone.localdate():
        raise ValidationError("این سررسید قابل ثبت نیست.")
    _positive(schedule.amount_toman)
    expense=Expense.objects.create(salon=salon,category=schedule.category,amount_toman=schedule.amount_toman,
        expense_date=expected_due,description=schedule.title)
    row=ExpenseOccurrence.objects.create(salon=salon,schedule=schedule,due_day=expected_due,expense=expense)
    jd=jdatetime.date.fromgregorian(date=expected_due)
    year,month=add_jalali_months(jd.year,jd.month,1)
    schedule.next_due=jdatetime.date(year,month,min(schedule.day_of_month,_jalali_days_in_month(year,month))).togregorian()
    schedule.save(update_fields=["next_due","updated_at"])
    _audit(salon,actor,expense,"expense","ثبت هزینه دوره‌ای",{"schedule_id":schedule.pk,"amount_toman":expense.amount_toman})
    return row
