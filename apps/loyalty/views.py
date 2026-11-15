from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.loyalty.forms import LoyaltyAdjustForm
from apps.loyalty.models import LoyaltyAccount, LoyaltyTransaction, ledger_adjust_points, transaction_signed_points
from apps.loyalty.services import loyalty_overview_stats, sync_account_tier, tier_count_rows
from apps.loyalty.tiers import LOYALTY_TIERS, next_tier_progress, tier_for_points
from apps.salons.decorators import salon_required
from apps.salons.permissions_policy import P_LOYALTY_MANAGE, require_permission


def _enrich_account(account: LoyaltyAccount) -> dict:
    tier = tier_for_points(account.points_balance)
    sync_account_tier(account)
    nxt, into, span = next_tier_progress(account.points_balance)
    return {
        "account": account,
        "tier": tier,
        "next_tier": nxt,
        "progress_into": into,
        "progress_span": span,
        "progress_pct": int(100 * into / span) if span else 100,
    }


@salon_required
@require_permission(P_LOYALTY_MANAGE)
def overview(request):
    salon = request.salon
    q = (request.GET.get("q") or "").strip()

    if request.method == "POST" and request.POST.get("action") == "adjust":
        form = LoyaltyAdjustForm(salon=salon, data=request.POST)
        if form.is_valid():
            customer = form.cleaned_data["customer"]
            delta = form.cleaned_data["points_delta"]
            note = form.cleaned_data["note"]
            try:
                ledger_adjust_points(salon=salon, customer=customer, points_delta=delta, note=note)
                messages.success(request, "امتیاز مشتری به‌روزرسانی شد.")
            except ValueError as exc:
                messages.error(request, "امتیاز کافی نیست." if "insufficient" in str(exc) else "مقدار امتیاز نامعتبر است.")
            return redirect(reverse("loyalty:overview") + (f"?q={q}" if q else ""))
    else:
        form = LoyaltyAdjustForm(salon=salon)

    stats = loyalty_overview_stats(salon)

    accounts_qs = (
        LoyaltyAccount.scoped(salon)
        .select_related("customer")
        .order_by("-points_balance", "customer__full_name")
    )
    if q:
        accounts_qs = accounts_qs.filter(
            Q(customer__full_name__icontains=q) | Q(customer__phone__icontains=q)
        )

    members = [_enrich_account(acc) for acc in accounts_qs[:80]]

    recent_transactions = (
        LoyaltyTransaction.scoped(salon)
        .select_related("account__customer")
        .order_by("-created_at")[:20]
    )
    recent_rows = []
    for tx in recent_transactions:
        recent_rows.append(
            {
                "tx": tx,
                "signed_points": transaction_signed_points(tx),
                "tier": tier_for_points(tx.account.points_balance),
            }
        )

    rules = [
        {"label": tier.label_fa, "min_points": tier.min_points}
        for tier in reversed(LOYALTY_TIERS)
    ]

    return render(
        request,
        "loyalty/overview.html",
        {
            "stats": stats,
            "tier_rows": tier_count_rows(stats),
            "members": members,
            "member_count": len(members),
            "total_members": stats.member_count,
            "recent_rows": recent_rows,
            "rules": rules,
            "search_q": q,
            "adjust_form": form,
        },
    )


@salon_required
@require_permission(P_LOYALTY_MANAGE)
def member_detail(request, pk: int):
    salon = request.salon
    account = get_object_or_404(
        LoyaltyAccount.scoped(salon).select_related("customer"),
        pk=pk,
    )
    ctx = _enrich_account(account)
    transactions = account.transactions.order_by("-created_at")[:100]
    tx_rows = [{"tx": tx, "signed_points": transaction_signed_points(tx)} for tx in transactions]
    return render(
        request,
        "loyalty/member_detail.html",
        {
            **ctx,
            "tx_rows": tx_rows,
        },
    )
