"""Campaign preparation only. Never use OTP providers for promotional messages."""
from datetime import timedelta
from uuid import UUID

import jdatetime
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.retention.models import Campaign, CampaignRecipient
from apps.retention.services import visit_customers
from apps.salons.models import SalonSettings

MAX_RECIPIENTS=5000


def segment_members(salon, segment):
    now=timezone.now()
    rows=visit_customers(salon)
    if segment==Campaign.Segment.ACTIVE:
        rows=rows.filter(actual_last_visit__gte=now-timedelta(days=30))
    elif segment==Campaign.Segment.AT_RISK:
        rows=rows.filter(actual_last_visit__lt=now-timedelta(days=30),actual_last_visit__gte=now-timedelta(days=60))
    elif segment==Campaign.Segment.INACTIVE:
        rows=rows.filter(actual_last_visit__lt=now-timedelta(days=60))
    elif segment==Campaign.Segment.NEW:
        rows=rows.filter(actual_last_visit__isnull=True)
    elif segment==Campaign.Segment.VIP:
        rows=rows.filter(is_vip=True)
    elif segment==Campaign.Segment.BIRTHDAY:
        month=jdatetime.date.fromgregorian(date=timezone.localdate()).month
        ids=[pk for pk,birth in rows.filter(birth_date__isnull=False).values_list("pk","birth_date") if jdatetime.date.fromgregorian(date=birth).month==month]
        rows=rows.filter(pk__in=ids)
    else:
        raise ValidationError("گروه مخاطبان نامعتبر است.")
    return rows


def eligible_members(salon, segment):
    return segment_members(salon,segment).filter(marketing_consent=True).exclude(phone="").order_by("pk")


def marketing_enabled(salon):
    return salon.is_active and SalonSettings.objects.filter(salon=salon,sms_marketing_enabled=True).exists()


def render_message(message,customer,salon):
    # Restricted placeholders; no arbitrary template execution.
    return message.replace("{name}",customer.full_name).replace("{salon}",salon.name)


@transaction.atomic
def create_campaign(*,salon,title,segment,message,request_key,actor):
    try:key=UUID(str(request_key))
    except (ValueError,TypeError,AttributeError):raise ValidationError("شناسه درخواست معتبر نیست.") from None
    title=title.strip()
    message=message.strip()
    if not title or len(title)>100 or not message or len(message)>480 or segment not in Campaign.Segment.values:
        raise ValidationError("اطلاعات کمپین معتبر نیست.")
    row,created=Campaign.objects.get_or_create(salon=salon,request_key=key,defaults={"title":title,"segment":segment,"message":message})
    if not created and (row.title,row.segment,row.message)!=(title,segment,message):
        raise ValidationError("درخواست قبلاً ثبت شده است.")
    if created:AuditLog.objects.create(salon=salon,actor=actor,action=AuditLog.Action.CREATE,entity_type="marketing_campaign",entity_id=str(row.pk),message="ایجاد پیش‌نویس کمپین")
    return row


@transaction.atomic
def prepare_campaign(*,salon,campaign_id,actor):
    row=Campaign.scoped(salon).select_for_update().filter(pk=campaign_id).first()
    if not row:raise ValidationError("کمپین یافت نشد.")
    if row.status==Campaign.Status.PREPARED:return row
    if row.status!=Campaign.Status.DRAFT:raise ValidationError("کمپین قابل آماده‌سازی نیست.")
    if not marketing_enabled(salon):raise ValidationError("ارسال تبلیغاتی در تنظیمات سالن غیرفعال است.")
    members=list(eligible_members(salon,row.segment)[:MAX_RECIPIENTS+1])
    if not members:raise ValidationError("هیچ مشتری واجد رضایت برای این گروه وجود ندارد.")
    if len(members)>MAX_RECIPIENTS:raise ValidationError("گروه مخاطبان بیش از سقف ۵۰۰۰ نفر است.")
    recipients=[]
    for customer in members:
        message=render_message(row.message,customer,salon)
        if len(message)>480:raise ValidationError("متن شخصی‌سازی‌شده بیش از ۴۸۰ کاراکتر است.")
        recipients.append(CampaignRecipient(salon=salon,campaign=row,customer=customer,message_snapshot=message))
    CampaignRecipient.objects.bulk_create(recipients,batch_size=500)
    row.status=Campaign.Status.PREPARED
    row.prepared_at=timezone.now()
    row.save(update_fields=["status","prepared_at","updated_at"])
    AuditLog.objects.create(salon=salon,actor=actor,action=AuditLog.Action.UPDATE,entity_type="marketing_campaign",entity_id=str(row.pk),message="آماده‌سازی مخاطبان کمپین",metadata={"count":len(recipients)})
    return row


@transaction.atomic
def cancel_campaign(*,salon,campaign_id,actor):
    row=Campaign.scoped(salon).select_for_update().filter(pk=campaign_id).first()
    if not row:raise ValidationError("کمپین یافت نشد.")
    if row.status!=Campaign.Status.CANCELLED:
        row.status=Campaign.Status.CANCELLED
        row.save(update_fields=["status","updated_at"])
        AuditLog.objects.create(salon=salon,actor=actor,action=AuditLog.Action.UPDATE,entity_type="marketing_campaign",entity_id=str(row.pk),message="لغو کمپین")
    return row



@transaction.atomic
def schedule_campaign(*, salon, campaign_id, scheduled_at, actor):
    """Explicit manager action; idempotent scheduling of a prepared snapshot."""
    if timezone.is_naive(scheduled_at):
        raise ValidationError("زمان ارسال باید دارای منطقه زمانی باشد.")
    now = timezone.now()
    if scheduled_at < now - timedelta(minutes=5) or scheduled_at > now + timedelta(days=90):
        raise ValidationError("زمان ارسال باید از اکنون تا ۹۰ روز آینده باشد.")
    row = Campaign.scoped(salon).select_for_update().filter(pk=campaign_id).first()
    if not row:
        raise ValidationError("کمپین یافت نشد.")
    if row.status == Campaign.Status.SCHEDULED and row.scheduled_at == scheduled_at:
        return row
    if row.status != Campaign.Status.PREPARED:
        raise ValidationError("کمپین باید ابتدا آماده‌سازی شده باشد.")
    if not marketing_enabled(salon):
        raise ValidationError("ارسال تبلیغاتی در تنظیمات سالن غیرفعال است.")
    if not row.recipients.filter(salon=salon).exists():
        raise ValidationError("کمپین مخاطب آماده ندارد.")
    row.status = Campaign.Status.SCHEDULED
    row.scheduled_at = scheduled_at
    row.save(update_fields=["status", "scheduled_at", "updated_at"])
    AuditLog.objects.create(
        salon=salon, actor=actor, action=AuditLog.Action.UPDATE,
        entity_type="marketing_campaign", entity_id=str(row.pk),
        message="زمان‌بندی کمپین", metadata={"scheduled_at": scheduled_at.isoformat()},
    )
    return row
