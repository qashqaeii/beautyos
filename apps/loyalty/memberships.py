from datetime import timedelta
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.customers.models import Customer
from apps.loyalty.automation import award_package
from apps.loyalty.models import MembershipCycle
from apps.packages.models import CustomerPackage, ServicePackage


@transaction.atomic
def buy_membership(*,salon,customer_id,package_id,request_key,actor,renewed_from_id=None):
    try:key=UUID(str(request_key))
    except (ValueError,TypeError,AttributeError):
        raise ValidationError("شناسه درخواست معتبر نیست.") from None
    customer=Customer.scoped(salon).select_for_update(no_key=True).filter(pk=customer_id,is_deleted=False).first()
    if not customer:raise ValidationError("مشتری معتبر نیست.")
    previous=MembershipCycle.scoped(salon).filter(request_key=key).select_related("purchase").first()
    if previous:
        if (previous.purchase.customer_id,previous.purchase.package_id,previous.renewed_from_id)!=(customer_id,package_id,renewed_from_id):
            raise ValidationError("درخواست قبلاً با اطلاعات متفاوت ثبت شده است.")
        return previous
    plan=ServicePackage.scoped(salon).filter(pk=package_id,is_active=True).first()
    if not plan or plan.price_toman<=0 or not 0<plan.session_count or not 0<plan.validity_days<=36500:
        raise ValidationError("پکیج فعال و معتبر انتخاب کنید.")
    now=timezone.now()
    prior=None
    if renewed_from_id:
        prior=MembershipCycle.scoped(salon).select_for_update(of=("self",)).select_related("purchase").filter(pk=renewed_from_id,purchase__customer=customer,purchase__package=plan).first()
        if not prior:raise ValidationError("دوره قبلی متعلق به همین عضویت نیست.")
        if MembershipCycle.scoped(salon).filter(renewed_from=prior).exists():
            raise ValidationError("این دوره قبلاً تمدید شده است.")
        if prior.purchase.is_valid():raise ValidationError("دوره قبلی هنوز جلسه و اعتبار دارد.")
    from django.db.models import F
    if CustomerPackage.scoped(salon).filter(customer=customer,package=plan,expires_at__gte=now,sessions_used__lt=F("sessions_total")).exists():
        raise ValidationError("مشتری در حال حاضر پکیج فعال مشابه دارد.")
    try:
        with transaction.atomic():
            purchase=CustomerPackage.objects.create(salon=salon,customer=customer,package=plan,sessions_total=plan.session_count,
                price_paid_toman=plan.price_toman,purchased_at=now,expires_at=now+timedelta(days=plan.validity_days))
            cycle=MembershipCycle.objects.create(salon=salon,purchase=purchase,renewed_from=prior,request_key=key)
    except IntegrityError as exc:
        raise ValidationError("این درخواست یا تمدید قبلاً ثبت شده است.") from exc
    award_package(purchase)
    AuditLog.objects.create(salon=salon,actor=actor,action=AuditLog.Action.CREATE,entity_type="membership_cycle",
        entity_id=str(cycle.pk),message="تمدید عضویت" if prior else "فروش عضویت",
        metadata={"package_purchase_id":purchase.pk,"amount_toman":purchase.price_paid_toman})
    return cycle
