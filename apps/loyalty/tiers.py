from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LoyaltyTier:
    key: str
    label_fa: str
    min_points: int


LOYALTY_TIERS: tuple[LoyaltyTier, ...] = (
    LoyaltyTier("platinum", "پلاتین", 1000),
    LoyaltyTier("gold", "طلایی", 500),
    LoyaltyTier("silver", "نقره‌ای", 200),
    LoyaltyTier("standard", "عضو عادی", 0),
)


def tier_for_points(points: int) -> LoyaltyTier:
    pts = max(0, int(points or 0))
    for tier in LOYALTY_TIERS:
        if pts >= tier.min_points:
            return tier
    return LOYALTY_TIERS[-1]


def next_tier_progress(points: int) -> tuple[LoyaltyTier | None, int, int]:
    """Return (next_tier, points_into_current_span, span_size) for progress UI."""
    current = tier_for_points(points)
    pts = max(0, int(points or 0))
    candidates = [t for t in LOYALTY_TIERS if t.min_points > current.min_points]
    if not candidates:
        return None, 0, 0
    nxt = min(candidates, key=lambda t: t.min_points)
    span = nxt.min_points - current.min_points
    into = min(max(pts - current.min_points, 0), span)
    return nxt, into, span
