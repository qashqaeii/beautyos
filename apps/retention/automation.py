"""Prepare source-linked notification intents; never send an SMS here."""
from datetime import timedelta

import jdatetime
from django.db import transaction
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.core.utils.dates import to_jalali_datetime
from apps.customers.models import Customer
from apps.retention.models import AutomationMessage, AutomationPolicy, FollowUp
from apps.retention.services import sync_follow_up_queue
from apps.salons.models import Salon, SalonSettings

BATCH_SIZE = 500


def reminder_key(appointment):
    return f"{appointment.pk}:{appointment.start_at.isoformat()}"


def birthday_key(customer, today):
    return f"{customer.pk}:{today.year}"


def winback_key(followup):
    return f"{followup.pk}:{followup.cycle_key}"


def future_booking(salon, customer, now):
    return Appointment.scoped(salon).filter(customer=customer,start_at__gte=now,
        status__in=[Appointment.Status.PENDING,Appointment.Status.CONFIRMED,Appointment.Status.CHECKED_IN]).exists()


def suppression_reason(row, policy, settings, now):
    """Recheck state before any future delivery; do not trust an old snapshot."""
    customer = row.customer
    salon = row.salon
    if not salon.is_active or customer.salon_id!=salon.pk or customer.is_deleted or not customer.phone:
        return "مشتری یا سالن غیرفعال"
    if now>=row.expires_at:
        return "مهلت ارسال گذشته است"
    if not policy or not settings:
        return "تنظیمات فعال نیست"
    if row.kind=="reminder":
        a=row.appointment
        if not policy.reminder_enabled or not settings.sms_transactional_enabled:
            return "یادآوری غیرفعال"
        if not a or a.salon_id!=salon.pk or a.customer_id!=customer.pk or a.status!=Appointment.Status.CONFIRMED or reminder_key(a)!=row.source_key or a.start_at<=now:
            return "نوبت تغییر کرده یا لغو شده است"
    else:
        if not settings.sms_marketing_enabled or not customer.marketing_consent:
            return "رضایت پیام تبلیغاتی موجود نیست"
        if row.kind=="birthday":
            today=jdatetime.date.fromgregorian(date=timezone.localdate(now))
            birth=jdatetime.date.fromgregorian(date=customer.birth_date) if customer.birth_date else None
            if not policy.birthday_enabled or not birth or (today.month,today.day)!=(birth.month,birth.day) or row.source_key!=birthday_key(customer,today):
                return "تاریخ تولد یا تنظیمات تغییر کرده است"
        elif row.kind=="winback":
            follow=row.followup
            if not policy.winback_enabled or not follow or follow.salon_id!=salon.pk or follow.customer_id!=customer.pk or follow.status!=FollowUp.Status.OPEN or winback_key(follow)!=row.source_key or future_booking(salon,customer,now):
                return "پیگیری دیگر واجد شرایط نیست"
        else:
            return "نوع پیام نامعتبر"
    return ""


def _enqueue(salon, customer, kind, source_key, text, due_at, expires_at, **links):
    if len(text)>480 or not customer.phone or customer.is_deleted:
        return 0
    _,created=AutomationMessage.objects.get_or_create(salon=salon,kind=kind,source_key=source_key,
        defaults={"customer":customer,"text":text,"due_at":due_at,"expires_at":expires_at,**links})
    return int(created)


@transaction.atomic
def prepare_automation(salon, now=None):
    """One durable intent per event; repeated scheduler runs do not duplicate it."""
    now=now or timezone.now()
    salon=Salon.objects.select_for_update(no_key=True).get(pk=salon.pk)
    policy=AutomationPolicy.scoped(salon).first()
    settings=SalonSettings.objects.filter(salon=salon).first()
    count=0
    if salon.is_active and policy and settings:
        if policy.reminder_enabled and settings.sms_transactional_enabled:
            appointments=Appointment.scoped(salon).filter(status=Appointment.Status.CONFIRMED,
                start_at__gt=now+timedelta(minutes=5),start_at__lte=now+timedelta(hours=24),
                customer__salon=salon,customer__is_deleted=False).exclude(customer__phone="").select_related("customer").order_by("start_at","pk")
            for a in appointments.iterator(chunk_size=BATCH_SIZE):
                count+=_enqueue(salon,a.customer,"reminder",reminder_key(a),
                    f"{a.customer.full_name} عزیز، یادآوری نوبت شما در {salon.name}، {to_jalali_datetime(a.start_at)}.",
                    now,a.start_at,appointment=a)
        if settings.sms_marketing_enabled and policy.birthday_enabled:
            today=jdatetime.date.fromgregorian(date=timezone.localdate(now))
            customers=Customer.scoped(salon).filter(is_deleted=False,marketing_consent=True,birth_date__isnull=False).exclude(phone="")
            for c in customers.iterator(chunk_size=BATCH_SIZE):
                birth=jdatetime.date.fromgregorian(date=c.birth_date)
                if (birth.month,birth.day)==(today.month,today.day):
                    count+=_enqueue(salon,c,"birthday",birthday_key(c,today),
                        f"{c.full_name} عزیز، تولدت مبارک! با آرزوی بهترین‌ها از طرف {salon.name}.",
                        now,now+timedelta(hours=24))
        if settings.sms_marketing_enabled and policy.winback_enabled:
            sync_follow_up_queue(salon)
            rows=FollowUp.scoped(salon).filter(status=FollowUp.Status.OPEN,days_since_visit__gte=60,
                customer__salon=salon,customer__is_deleted=False,customer__marketing_consent=True).exclude(cycle_key="").exclude(customer__phone="").select_related("customer")
            for row in rows.iterator(chunk_size=BATCH_SIZE):
                if not future_booking(salon,row.customer,now):
                    count+=_enqueue(salon,row.customer,"winback",winback_key(row),
                        f"{row.customer.full_name} عزیز، خوشحال می‌شویم دوباره در {salon.name} ببینیمتان.",
                        now,now+timedelta(days=7),followup=row)
    for row in AutomationMessage.scoped(salon).filter(status="pending").select_related("customer","salon","appointment","followup").iterator(chunk_size=BATCH_SIZE):
        reason=suppression_reason(row,policy,settings,now)
        if reason:
            AutomationMessage.scoped(salon).filter(pk=row.pk,status="pending").update(status="skipped",reason=reason,updated_at=now)
    return count
