"""Read-only loyalty insights with mutually exclusive visit segments."""
from datetime import timedelta

from django.db.models import Count, F, Max, Q, Sum
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.customers.models import Customer
from apps.loyalty.models import LoyaltyAccount,LoyaltyTransaction,MembershipCycle,Referral,RewardRedemption,LoyaltyVoucher
from apps.core.utils.dates import jalali_month_bounds


def loyalty_insights(salon):
    now=timezone.now()
    customers=Customer.scoped(salon).filter(is_deleted=False)
    completed=Q(appointments__salon=salon,appointments__status=Appointment.Status.COMPLETED)
    rows=customers.annotate(visit_count=Count("appointments",filter=completed),
        last_visit=Max("appointments__start_at",filter=completed))
    segments=[
        {"label":"بدون مراجعه انجام‌شده","count":rows.filter(visit_count=0).count()},
        {"label":"فعال · ۳۰ روز اخیر","count":rows.filter(last_visit__gte=now-timedelta(days=30)).count()},
        {"label":"نیازمند پیگیری · ۳۱ تا ۶۰ روز","count":rows.filter(last_visit__lt=now-timedelta(days=30),last_visit__gte=now-timedelta(days=60)).count()},
        {"label":"غیرفعال · بیش از ۶۰ روز","count":rows.filter(last_visit__lt=now-timedelta(days=60)).count()},
    ]
    total=customers.count()
    for row in segments:row["percent"]=round(100*row["count"]/total,1) if total else 0
    visited=total-segments[0]["count"]
    repeat=rows.filter(visit_count__gte=2).count()
    member_qs=LoyaltyAccount.scoped(salon).filter(customer__is_deleted=False,customer__salon=salon)
    refs=Referral.scoped(salon)
    count=refs.count()
    confirmed=refs.filter(status="awarded").count()
    cycles=MembershipCycle.scoped(salon)
    first,last=jalali_month_bounds()
    points=LoyaltyTransaction.scoped(salon).filter(created_at__date__range=(first,last))
    return {
        "total":total,"segments":segments,"visited":visited,"repeat":repeat,
        "repeat_rate":round(100*repeat/visited,1) if visited else 0,
        "member_count":member_qs.count(),"vip_count":customers.filter(is_vip=True).count(),
        "referrals":count,"confirmed_referrals":confirmed,"referral_rate":round(confirmed*100/count,1) if count else 0,
        "active_cycles":cycles.filter(purchase__customer__is_deleted=False,purchase__expires_at__gte=now,purchase__sessions_used__lt=F("purchase__sessions_total")).count(),
        "fulfilled_rewards":RewardRedemption.scoped(salon).filter(status="fulfilled").count(),
        "used_vouchers":LoyaltyVoucher.scoped(salon).filter(invoice__isnull=False).count(),
        "earned_month":points.filter(kind="earn").aggregate(value=Sum("points"))["value"] or 0,
        "spent_month":points.filter(kind="redeem").aggregate(value=Sum("points"))["value"] or 0,
        "top":rows.filter(visit_count__gt=0).order_by("-total_spent_toman","-visit_count","pk")[:10],
        "at_risk":rows.filter(last_visit__lt=now-timedelta(days=30)).order_by("-last_visit","pk")[:20],
    }
