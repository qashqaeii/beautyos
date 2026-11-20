from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.loyalty.models import LoyaltyAccount, LoyaltyTransaction
from apps.loyalty.tiers import LOYALTY_TIERS, tier_for_points


@dataclass
class LoyaltyOverviewStats:
    member_count: int
    total_points: int
    avg_points: int
    points_earned_month: int
    points_redeemed_month: int
    active_with_balance: int
    tier_counts: dict[str, int]


def sync_account_tier(account: LoyaltyAccount) -> bool:
    tier = tier_for_points(account.points_balance)
    if account.tier != tier.key:
        account.tier = tier.key
        account.save(update_fields=["tier", "updated_at"])
        return True
    return False


def loyalty_overview_stats(salon) -> LoyaltyOverviewStats:
    accounts = LoyaltyAccount.scoped(salon)
    agg = accounts.aggregate(
        member_count=Count("id"),
        total_points=Sum("points_balance", filter=Q(points_balance__gt=0)),
        active_with_balance=Count("id", filter=Q(points_balance__gt=0)),
    )
    member_count = agg["member_count"] or 0
    total_points = int(agg["total_points"] or 0)
    active_with_balance = agg["active_with_balance"] or 0
    avg_points = int(total_points / member_count) if member_count else 0

    from apps.core.utils.dates import jalali_month_bounds
    month_start, month_end = jalali_month_bounds()
    txs = LoyaltyTransaction.scoped(salon).filter(created_at__date__range=(month_start, month_end))
    points_earned_month = int(
        txs.filter(kind=LoyaltyTransaction.Kind.EARN).aggregate(s=Sum("points"))["s"] or 0
    )
    points_redeemed_month = int(
        txs.filter(kind=LoyaltyTransaction.Kind.REDEEM).aggregate(s=Sum("points"))["s"] or 0
    )

    tier_counts: Counter[str] = Counter()
    for bal in accounts.values_list("points_balance", flat=True):
        tier_counts[tier_for_points(bal).key] += 1
    return LoyaltyOverviewStats(
        member_count=member_count,
        total_points=total_points,
        avg_points=avg_points,
        points_earned_month=points_earned_month,
        points_redeemed_month=points_redeemed_month,
        active_with_balance=active_with_balance,
        tier_counts=dict(tier_counts),
    )


def tier_count_rows(stats: LoyaltyOverviewStats) -> list[dict]:
    rows = []
    for tier in LOYALTY_TIERS:
        rows.append(
            {
                "key": tier.key,
                "label": tier.label_fa,
                "min_points": tier.min_points,
                "count": stats.tier_counts.get(tier.key, 0),
            }
        )
    return rows
