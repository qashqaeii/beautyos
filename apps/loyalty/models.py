from django.db import models

from apps.core.models import TimeStampedModel
from apps.core.tenant import TenantModelMixin


class LoyaltyAccount(TenantModelMixin, TimeStampedModel):
    customer = models.OneToOneField("customers.Customer", on_delete=models.CASCADE, related_name="loyalty")
    points_balance = models.IntegerField(default=0)
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
    points = models.IntegerField()
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

    if points <= 0:
        raise ValueError("points must be positive for earn")

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

    if points <= 0:
        raise ValueError("points must be positive for redeem")

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

    if points_delta == 0:
        raise ValueError("points_delta cannot be zero")

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
