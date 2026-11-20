from django.db import models

from apps.core.models import TimeStampedModel
from apps.core.tenant import TenantModelMixin


class LoyaltyAccount(TenantModelMixin, TimeStampedModel):
    customer = models.OneToOneField("customers.Customer", on_delete=models.CASCADE, related_name="loyalty")
    points_balance = models.BigIntegerField(default=0)
    tier = models.CharField(max_length=32, default="standard")

    class Meta:
        indexes = [models.Index(fields=["salon", "-points_balance"])]


class LoyaltyTransaction(TenantModelMixin, TimeStampedModel):
    class Kind(models.TextChoices):
        EARN = "earn", "امتیاز"
        REDEEM = "redeem", "مصرف"
        ADJUST = "adjust", "اصلاح"

    account = models.ForeignKey(LoyaltyAccount, on_delete=models.PROTECT, related_name="transactions")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    points = models.BigIntegerField()
    reference = models.CharField(max_length=64, blank=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        indexes = [models.Index(fields=["salon", "account", "-created_at"])]


def _refresh_tier_after_balance_change(account: LoyaltyAccount) -> None:
    from apps.loyalty.tiers import tier_for_points

    tier_key = tier_for_points(account.points_balance).key
    if account.tier != tier_key:
        LoyaltyAccount.objects.filter(pk=account.pk).update(tier=tier_key)


def ledger_add_points(*, salon, customer, points: int, reference: str = "", note: str = "") -> LoyaltyTransaction:
    from django.db import transaction
    from django.db.models import F

    if not isinstance(points, int) or not 0 < points <= 1000000000:
        raise ValueError("points must be positive for earn")

    if customer.salon_id != salon.pk:
        raise ValueError("customer belongs to another salon")

    with transaction.atomic():
        account, _ = LoyaltyAccount.objects.select_for_update().get_or_create(
            salon=salon, customer=customer, defaults={"points_balance": 0}
        )
        LoyaltyAccount.objects.filter(pk=account.pk).update(points_balance=F("points_balance") + points)
        account.refresh_from_db()
        _refresh_tier_after_balance_change(account)
        return LoyaltyTransaction.objects.create(
            salon=salon,
            account=account,
            kind=LoyaltyTransaction.Kind.EARN,
            points=points,
            reference=reference,
            note=note,
        )


def ledger_redeem_points(*, salon, customer, points: int, reference: str = "", note: str = "") -> LoyaltyTransaction:
    from django.db import transaction
    from django.db.models import F

    if not isinstance(points, int) or not 0 < points <= 1000000000:
        raise ValueError("points must be positive for redeem")

    if customer.salon_id != salon.pk:
        raise ValueError("customer belongs to another salon")

    with transaction.atomic():
        account = LoyaltyAccount.objects.select_for_update().get(salon=salon, customer=customer)
        if account.points_balance < points:
            raise ValueError("insufficient points")
        LoyaltyAccount.objects.filter(pk=account.pk).update(points_balance=F("points_balance") - points)
        account.refresh_from_db()
        _refresh_tier_after_balance_change(account)
        return LoyaltyTransaction.objects.create(
            salon=salon,
            account=account,
            kind=LoyaltyTransaction.Kind.REDEEM,
            points=points,
            reference=reference,
            note=note,
        )


def ledger_adjust_points(*, salon, customer, points_delta: int, note: str = "") -> LoyaltyTransaction:
    from django.db import transaction
    from django.db.models import F

    if not isinstance(points_delta, int) or not 0 < abs(points_delta) <= 1000000000:
        raise ValueError("points_delta invalid")

    if customer.salon_id != salon.pk:
        raise ValueError("customer belongs to another salon")

    with transaction.atomic():
        account, _ = LoyaltyAccount.objects.select_for_update().get_or_create(
            salon=salon, customer=customer, defaults={"points_balance": 0}
        )
        if points_delta < 0 and account.points_balance + points_delta < 0:
            raise ValueError("insufficient points")
        LoyaltyAccount.objects.filter(pk=account.pk).update(points_balance=F("points_balance") + points_delta)
        account.refresh_from_db()
        _refresh_tier_after_balance_change(account)
        return LoyaltyTransaction.objects.create(
            salon=salon,
            account=account,
            kind=LoyaltyTransaction.Kind.ADJUST,
            points=abs(points_delta),
            reference=str(points_delta),
            note=note,
        )


def transaction_signed_points(tx: LoyaltyTransaction) -> int:
    if tx.kind == LoyaltyTransaction.Kind.EARN:
        return tx.points
    if tx.kind == LoyaltyTransaction.Kind.REDEEM:
        return -tx.points
    if tx.kind == LoyaltyTransaction.Kind.ADJUST:
        try:
            return int(tx.reference)
        except (TypeError, ValueError):
            return tx.points
    return tx.points


class LoyaltyPolicy(TenantModelMixin, TimeStampedModel):
    enabled = models.BooleanField(default=False)
    spend_per_point_toman = models.BigIntegerField(default=100000)
    visit_points = models.PositiveIntegerField(default=0)
    birthday_points = models.PositiveIntegerField(default=0)
    referral_points = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["salon"], name="loyalty_one_policy_per_salon"),
            models.CheckConstraint(condition=models.Q(spend_per_point_toman__gte=1000), name="loyalty_min_spend_unit"),
        ]


class LoyaltyAward(TenantModelMixin, TimeStampedModel):
    """Original entitlement and remaining entitlement after reversals."""
    account = models.ForeignKey(LoyaltyAccount, on_delete=models.PROTECT, related_name="awards")
    source_kind = models.CharField(max_length=16)
    source_key = models.CharField(max_length=64)
    original_points = models.PositiveIntegerField(default=0)
    remaining_points = models.PositiveIntegerField(default=0)
    spend_unit_toman = models.BigIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["salon", "source_kind", "source_key"], name="loyalty_unique_source_award"),
            models.CheckConstraint(condition=models.Q(remaining_points__lte=models.F("original_points")), name="loyalty_award_remaining"),
        ]


class LoyaltyReward(TenantModelMixin, TimeStampedModel):
    title = models.CharField(max_length=100)
    description = models.CharField(max_length=255, blank=True)
    points_cost = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(points_cost__gt=0), name="loyalty_reward_cost_positive")]


class RewardRedemption(TenantModelMixin, TimeStampedModel):
    reward = models.ForeignKey("loyalty.LoyaltyReward", on_delete=models.PROTECT, related_name="redemptions")
    account = models.ForeignKey("loyalty.LoyaltyAccount", on_delete=models.PROTECT, related_name="redemptions")
    title_snapshot = models.CharField(max_length=100)
    points_cost = models.PositiveIntegerField()
    request_key = models.UUIDField()
    status = models.CharField(max_length=12, choices=[("pending","در انتظار تحویل"),("fulfilled","تحویل‌شده"),("cancelled","لغوشده")], default="pending")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["salon","request_key"],name="loyalty_redemption_request"), models.CheckConstraint(condition=models.Q(points_cost__gt=0),name="loyalty_redemption_cost_positive")]


class Referral(TenantModelMixin, TimeStampedModel):
    referrer = models.ForeignKey("customers.Customer", on_delete=models.PROTECT, related_name="loyalty_referrals")
    referred = models.OneToOneField("customers.Customer", on_delete=models.PROTECT, related_name="loyalty_referral")
    qualifying_visit = models.OneToOneField("appointments.Appointment", on_delete=models.PROTECT, null=True, blank=True, related_name="loyalty_referral")
    points_snapshot = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=[("pending","در انتظار مراجعه"),("awarded","پاداش ثبت شد"),("reversed","برگشت پاداش")],default="pending")

    class Meta:
        constraints = [models.CheckConstraint(condition=~models.Q(referrer=models.F("referred")),name="loyalty_referral_not_self")]


class LoyaltyVoucher(TenantModelMixin, TimeStampedModel):
    customer = models.ForeignKey("customers.Customer", on_delete=models.PROTECT, related_name="loyalty_vouchers")
    title = models.CharField(max_length=100)
    amount_toman = models.BigIntegerField()
    expires_on = models.DateField()
    is_active = models.BooleanField(default=True)
    invoice = models.OneToOneField("finance.Invoice", on_delete=models.PROTECT, null=True, blank=True, related_name="loyalty_voucher")

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(amount_toman__gt=0),name="loyalty_voucher_positive")]


class MembershipCycle(TenantModelMixin, TimeStampedModel):
    """A renewable membership is an ordinary paid package, not a second charge."""
    purchase = models.OneToOneField("packages.CustomerPackage", on_delete=models.PROTECT, related_name="membership_cycle")
    renewed_from = models.OneToOneField("self", on_delete=models.PROTECT, null=True, blank=True, related_name="renewal")
    request_key = models.UUIDField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["salon","request_key"],name="loyalty_membership_request")]
