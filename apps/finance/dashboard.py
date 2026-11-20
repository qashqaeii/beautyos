"""Read-only management projections, not a second accounting ledger."""
from collections import defaultdict
from datetime import timedelta

from django.db.models import Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.commissions.models import CommissionEntry, CommissionSettlement
from apps.dashboard.role_services import appointment_payment_summary
from apps.expenses.models import Expense
from apps.finance.models import Payment, SalonDebtPayment
from apps.finance.services import open_debts_summary
from apps.packages.models import CustomerPackage, PackageSessionUse


def _total(qs, field):
    return int(qs.aggregate(value=Sum(field))["value"] or 0)


def _chart(receipts, expenses, first, last):
    """Actual daily/weekly buckets on a shared zero-based scale."""
    days = max(1, (last - first).days + 1)
    period = max(1, (days + 6) // 7)
    incoming = dict(receipts.order_by().annotate(
        day=TruncDate("created_at", tzinfo=timezone.get_current_timezone())
    ).values("day").annotate(value=Sum("paid_amount_toman")).values_list("day", "value"))
    outgoing = dict(expenses.order_by().values("expense_date").annotate(
        value=Sum("amount_toman")).values_list("expense_date", "value"))
    rows = []
    for offset in range(0, days, period):
        day = first + timedelta(days=offset)
        end = min(last, day + timedelta(days=period - 1))
        rows.append({"day": day, "end": end,
            "received": sum(incoming.get(day + timedelta(days=i), 0) for i in range((end-day).days+1)),
            "expense": sum(outgoing.get(day + timedelta(days=i), 0) for i in range((end-day).days+1))})
    peak = max([1] + [max(r["received"], r["expense"]) for r in rows])
    for index, row in enumerate(rows):
        row["x"] = round(200 if len(rows) == 1 else 15 + index * 370 / (len(rows)-1), 2)
        row["received_y"] = round(120 - max(0, row["received"]) * 102 / peak, 2)
        row["expense_y"] = round(120 - max(0, row["expense"]) * 102 / peak, 2)
    def points(key):
        return " ".join(f"{row['x']},{row[key]}" for row in rows)
    return {"rows": rows, "peak": peak, "received_points": points("received_y"),
            "expense_points": points("expense_y"),
            "received_area": f"{rows[0]['x']},120 {points('received_y')} {rows[-1]['x']},120",
            "has_data": any(r["received"] or r["expense"] for r in rows)}


def finance_dashboard(salon, range_ctx):
    start, end = range_ctx["start_dt"], range_ctx["end_dt"]
    first, last = range_ctx["start_date"], range_ctx["end_date"]
    receipts = Payment.scoped(salon).filter(
        created_at__gte=start, created_at__lt=end, paid_amount_toman__gt=0
    ).exclude(status=Payment.Status.REFUNDED)
    expenses = Expense.scoped(salon).filter(expense_date__range=(first, last))
    completed = Appointment.scoped(salon).filter(status=Appointment.Status.COMPLETED).filter(
        Q(completed_at__gte=start, completed_at__lt=end) |
        Q(completed_at__isnull=True, start_at__gte=start, start_at__lt=end)
    ).select_related("service", "customer").prefetch_related("payments")
    package_uses = {u.appointment_id: u for u in PackageSessionUse.scoped(salon).filter(
        appointment__in=completed.values("pk"), customer_package__salon=salon
    ).select_related("customer_package")}
    earned = 0
    service_rows = defaultdict(lambda: {"revenue": 0, "commission": 0, "count": 0})
    completed_ids = []
    by_service = {}
    for appt in completed:
        completed_ids.append(appt.pk)
        by_service[appt.pk] = appt.service_id
        row = service_rows[appt.service_id]
        row["name"] = appt.service.name
        row["count"] += 1
        use = package_uses.get(appt.pk)
        if use:
            # Recognize the prepaid value per redeemed session, not the face price again.
            package = use.customer_package
            value = max(0, int(package.price_paid_toman)) // max(1, package.sessions_total)
        else:
            discount = sum(max(0, p.discount_toman) for p in appt.payments.all()
                           if p.salon_id == salon.pk and p.customer_id == appt.customer_id
                           and p.status != Payment.Status.REFUNDED)
            value = max(0, int(appt.price_toman) - discount)
        row["revenue"] += value
        earned += value
    commission = 0
    for entry in CommissionEntry.scoped(salon).filter(
        appointment_id__in=completed_ids
    ).exclude(status=CommissionEntry.Status.VOID):
        amount = int(entry.commission_amount_toman)
        commission += amount
        service_rows[by_service[entry.appointment_id]]["commission"] += amount
    for row in service_rows.values():
        row["contribution"] = row["revenue"] - row["commission"]
    expenses_total = _total(expenses, "amount_toman")
    received = _total(receipts, "paid_amount_toman")
    method_totals = dict(receipts.order_by().values("method").annotate(
        total=Sum("paid_amount_toman")).values_list("method", "total"))
    methods = [{"name": label, "amount": int(method_totals.get(key, 0)),
                "percent": round(int(method_totals.get(key, 0)) * 100 / received, 1) if received else 0}
               for key, label in Payment.Method.choices]
    # Open receivables are current balances of completed non-package appointments.
    # Future bookings and unused prepaid sessions are not debts.
    receivables = []
    owing = Appointment.scoped(salon).filter(status=Appointment.Status.COMPLETED,
        package_use__isnull=True).select_related("customer", "service").prefetch_related("payments")
    for appt in owing:
        balance = appointment_payment_summary(appt)["owed_toman"]
        if balance:
            receivables.append({"appointment": appt, "amount": balance})
    receivables.sort(key=lambda row: row["appointment"].start_at)
    debt = open_debts_summary(salon)
    staff_due = defaultdict(int)
    staff_names = {}
    for entry in CommissionEntry.scoped(salon).filter(status=CommissionEntry.Status.RECOGNIZED).select_related("staff"):
        staff_due[entry.staff_id] += int(entry.commission_amount_toman) - int(entry.settled_amount_toman)
        staff_names[entry.staff_id] = entry.staff.full_display_name
    staff_rows = sorted([{"name": staff_names[key], "amount": amount, "staff_id": key}
                         for key, amount in staff_due.items() if amount > 0], key=lambda row: -row["amount"])
    package_sales = _total(CustomerPackage.scoped(salon).filter(
        purchased_at__gte=start, purchased_at__lt=end), "price_paid_toman")
    paid_commissions = _total(CommissionSettlement.scoped(salon).filter(
        settled_at__gte=start, settled_at__lt=end), "amount_toman")
    paid_debt = _total(SalonDebtPayment.scoped(salon).filter(
        created_at__gte=start, created_at__lt=end), "amount_toman")
    return {
        "received": received, "earned": earned, "expenses": expenses_total, "commission": commission,
        "operating_estimate": earned - expenses_total - commission,
        "receipt_count": receipts.count(), "methods": methods,
        "method_cut1": round(method_totals.get("cash", 0) * 100 / received, 2) if received else 0,
        "method_cut2": round((method_totals.get("cash", 0) + method_totals.get("card", 0)) * 100 / received, 2) if received else 0,
        "package_sales": package_sales,
        "paid_commissions": paid_commissions, "paid_debt": paid_debt,
        "receivable_total": sum(row["amount"] for row in receivables),
        "receivables": receivables[:30], "receivable_count": len(receivables),
        "debt_total": debt["total_balance"], "debts": debt["open_debts"][:4],
        "staff_due_total": sum(row["amount"] for row in staff_rows), "staff_due": staff_rows[:5],
        "recent_expenses": expenses.order_by("-expense_date", "-pk")[:4],
        "service_rows": sorted(service_rows.values(), key=lambda row: -row["revenue"]),
        "chart": _chart(receipts, expenses, first, last),
    }
