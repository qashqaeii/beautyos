"""Prepare source-linked notification intents; never send an SMS here."""
from datetime import timedelta

import jdatetime
from django.db import transaction
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.core.utils.dates import to_jalali_datetime
from apps.customers.models import Customer
from apps.retention.models import AutomationMessage, AutomationPolicy, Campaign, CampaignRecipient, FollowUp
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
    """Review current tenant, opt-in and source state at dispatch time."""
    customer, salon = row.customer, row.salon
    if not salon.is_active or customer.salon_id != salon.pk or customer.is_deleted or not customer.phone:
        return "مشتری یا سالن غیرفعال"
    if now >= row.expires_at:
        return "مهلت ارسال گذشته است"
    if not settings or (not policy and row.kind != "campaign"):
        return "تنظیمات فعال نیست"

    if row.kind in ("reminder", "confirmation", "cancellation"):
        a = row.appointment
        if not settings.sms_transactional_enabled or not a or a.salon_id != salon.pk or a.customer_id != customer.pk:
            return "اطلاع‌رسانی نوبت مجاز نیست"
        if row.kind == "reminder":
            if not policy.reminder_enabled or a.status != Appointment.Status.CONFIRMED or reminder_key(a) != row.source_key or a.start_at <= now:
                return "نوبت تغییر کرده یا لغو شده است"
        elif row.kind == "confirmation":
            if not policy.confirmation_enabled or a.status != Appointment.Status.CONFIRMED or reminder_key(a) != row.source_key or a.start_at <= now:
                return "تأیید نوبت دیگر معتبر نیست"
        else:
            expected = f"{a.pk}:{a.cancelled_at.isoformat()}" if a.cancelled_at else ""
            if not policy.cancellation_enabled or a.status != Appointment.Status.CANCELLED or row.source_key != expected:
                return "لغو نوبت دیگر معتبر نیست"
        return ""

    if not settings.sms_marketing_enabled or not customer.marketing_consent:
        return "رضایت پیام تبلیغاتی موجود نیست"
    if row.kind == "birthday":
        today = jdatetime.date.fromgregorian(date=timezone.localdate(now))
        birth = jdatetime.date.fromgregorian(date=customer.birth_date) if customer.birth_date else None
        if not policy.birthday_enabled or not birth or (today.month, today.day) != (birth.month, birth.day) or row.source_key != birthday_key(customer, today):
            return "تاریخ تولد یا تنظیمات تغییر کرده است"
    elif row.kind == "winback":
        follow = row.followup
        if not policy.winback_enabled or not follow or follow.salon_id != salon.pk or follow.customer_id != customer.pk or follow.status != FollowUp.Status.OPEN or winback_key(follow) != row.source_key or future_booking(salon, customer, now):
            return "پیگیری دیگر واجد شرایط نیست"
    elif row.kind == "campaign":
        recipient = row.campaign_recipient
        if not recipient or recipient.salon_id != salon.pk or recipient.customer_id != customer.pk:
            return "گیرنده کمپین نامعتبر است"
        campaign = recipient.campaign
        if campaign.salon_id != salon.pk or campaign.status != Campaign.Status.SCHEDULED or row.source_key != f"{campaign.pk}:{recipient.pk}":
            return "کمپین لغو یا تغییر کرده است"
    else:
        return "نوع پیام نامعتبر"
    return ""


def _enqueue(salon, customer, kind, source_key, text, due_at, expires_at, **links):
    if len(text)>480 or not customer.phone or customer.is_deleted:
        return 0
    _,created=AutomationMessage.objects.get_or_create(salon=salon,kind=kind,source_key=source_key,
        defaults={"customer":customer,"text":text,"due_at":due_at,"expires_at":expires_at,**links})
    return int(created)


def queue_appointment_event(appointment, kind, now=None):
    """Only newly-created/transitioned appointments trigger transactional SMS."""
    if kind not in ("confirmation", "cancellation"):
        raise ValueError("Invalid appointment event")
    now = now or timezone.now()
    salon = appointment.salon
    policy = AutomationPolicy.scoped(salon).first()
    settings = SalonSettings.objects.filter(salon=salon).first()
    if not salon.is_active or not settings or not settings.sms_transactional_enabled or not policy:
        return 0
    if not getattr(policy, f"{kind}_enabled") or appointment.start_at <= now:
        return 0
    if kind == "confirmation":
        if appointment.status != Appointment.Status.CONFIRMED:
            return 0
        source_key = reminder_key(appointment)
        text = f"{appointment.customer.full_name} عزیز، نوبت شما در {salon.name} برای {to_jalali_datetime(appointment.start_at)} تأیید شد."
        expiry = min(appointment.start_at, now + timedelta(hours=24))
    else:
        if appointment.status != Appointment.Status.CANCELLED or not appointment.cancelled_at:
            return 0
        source_key = f"{appointment.pk}:{appointment.cancelled_at.isoformat()}"
        text = f"{appointment.customer.full_name} عزیز، نوبت {to_jalali_datetime(appointment.start_at)} شما در {salon.name} لغو شد."
        expiry = now + timedelta(hours=24)
    return _enqueue(salon, appointment.customer, kind, source_key, text, now, expiry, appointment=appointment)


def prepare_scheduled_campaigns(salon, now):
    count = 0
    campaigns = Campaign.scoped(salon).filter(status=Campaign.Status.SCHEDULED, scheduled_at__lte=now).order_by("pk")
    for campaign in campaigns.iterator(chunk_size=100):
        recipients = CampaignRecipient.scoped(salon).filter(
            campaign=campaign, customer__salon=salon, customer__is_deleted=False,
            customer__marketing_consent=True,
        ).exclude(customer__phone="").select_related("customer")
        for recipient in recipients.iterator(chunk_size=BATCH_SIZE):
            count += _enqueue(salon, recipient.customer, "campaign", f"{campaign.pk}:{recipient.pk}",
                              recipient.message_snapshot, campaign.scheduled_at,
                              campaign.scheduled_at + timedelta(hours=24), campaign_recipient=recipient)
    return count


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
    if salon.is_active and settings and settings.sms_marketing_enabled:
        count += prepare_scheduled_campaigns(salon, now)
    for row in AutomationMessage.scoped(salon).filter(status="pending").select_related("customer","salon","appointment","followup","campaign_recipient__campaign").iterator(chunk_size=BATCH_SIZE):
        reason=suppression_reason(row,policy,settings,now)
        if reason:
            AutomationMessage.scoped(salon).filter(pk=row.pk,status="pending").update(status="skipped",reason=reason,updated_at=now)
    return count
