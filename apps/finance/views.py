from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Sum
from django.http import QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from apps.commissions.services import create_settlement
from apps.finance.dashboard import finance_dashboard
from apps.finance.forms import PaymentForm, SalonDebtForm, SalonDebtPaymentForm
from apps.finance.models import Invoice, Payment, SalonDebt
from apps.finance.services import (
    commission_day_overview,
    customer_payment_queryset,
    income_metrics,
    income_presentation,
    open_debts_summary,
    parse_finance_range,
    record_salon_debt_payment,
    record_customer_payment,
)
from apps.salons.decorators import salon_required
from apps.salons.models import SalonMembership
from apps.salons.permissions import require_role
from apps.salons.permissions_policy import (
    P_COMMISSION_MANAGE,
    P_FINANCE_REPORTS,
    P_PAYMENT_CREATE,
    P_PAYMENT_VIEW,
    P_EXPENSE_MANAGE,
    has_permission,
)
from apps.staff.models import StaffProfile


def _positive_pk(raw):
    from django.http import Http404

    try:
        pk = int(raw)
    except (TypeError, ValueError):
        raise Http404 from None
    if not 0 < pk <= 2**63 - 1:
        raise Http404
    return pk


def _finance_redirect(**params):
    base = reverse("finance:overview")
    if not params:
        return base
    return f"{base}?{urlencode(params)}"


def _finance_return_url(get_query: QueryDict) -> str:
    q = get_query.copy()
    q.pop("payment", None)
    base = reverse("finance:overview")
    qs = q.urlencode()
    return f"{base}?{qs}" if qs else base


def _append_payment_query(url: str) -> str:
    parts = urlparse(url)
    q = dict(parse_qsl(parts.query, keep_blank_values=True))
    q["payment"] = "1"
    path = parts.path or reverse("finance:overview")
    qs = urlencode(q)
    return f"{path}?{qs}" if qs else path


def _is_finance_overview_path(path: str) -> bool:
    return path.rstrip("/") == reverse("finance:overview").rstrip("/")


def _finance_get_from_post(post) -> QueryDict:
    qd = QueryDict(mutable=True)
    qd["tab"] = post.get("finance_tab", "income")
    qd["range"] = post.get("finance_range", "today")
    qd["rows"] = post.get("finance_rows", "5")
    qd["page"] = post.get("finance_page", "1")
    day = post.get("finance_day")
    if day:
        qd["day"] = day
    return qd


class _FinanceGetRequest:
    def __init__(self, request, get_query: QueryDict):
        self.__dict__.update(request.__dict__)
        self.GET = get_query


def _finance_overview_context(
    request,
    *,
    get_query=None,
    payment_form=None,
    payment_modal_open: bool = False,
    debt_form=None,
    debt_form_open: bool = False,
):
    get_query = (request.GET if get_query is None else get_query).copy()
    tab = get_query.get("tab", "income")
    if tab not in ("income", "cash", "debts", "commissions", "reports", "receipts"):
        tab = "income"
    if tab in ("commissions", "cash") and get_query.get("range", "today") not in ("today", "day"):
        get_query["range"] = "day"
    range_ctx = parse_finance_range(_FinanceGetRequest(request, get_query))

    membership = getattr(request, "membership", None)
    can_manage_debt = has_permission(membership, P_FINANCE_REPORTS)
    if not can_manage_debt:
        raise PermissionDenied
    can_settle_commission = has_permission(membership, P_COMMISSION_MANAGE)
    can_payment_create = has_permission(membership, P_PAYMENT_CREATE)

    if payment_modal_open and can_payment_create and payment_form is None:
        payment_form = PaymentForm(salon=request.salon)

    if debt_form is None:
        debt_form = SalonDebtForm()
    # Only query the active tab. The other panels are not rendered.
    income = income_metrics(request.salon, range_ctx["start_dt"], range_ctx["end_dt"]) if tab in ("income", "cash", "receipts", "reports") else None
    payments = ()
    payment_page = None
    payment_page_size = 50 if get_query.get("rows") == "50" else 5
    presentation = None
    cash_query = get_query.get("q", "").strip()[:100] if tab == "cash" else ""
    cash_partial_total = cash_paid_total = cash_invoice_total = 0
    if tab in ("income", "cash", "receipts", "reports"):
        queryset = customer_payment_queryset(request.salon, range_ctx["start_dt"], range_ctx["end_dt"])
        if tab == "cash":
            cash_partial_total = queryset.filter(status=Payment.Status.PARTIAL).aggregate(total=Sum("paid_amount_toman"))["total"] or 0
            cash_paid_total = queryset.filter(status=Payment.Status.PAID).aggregate(total=Sum("paid_amount_toman"))["total"] or 0
            cash_invoice_total = Invoice.scoped(request.salon).filter(created_at__gte=range_ctx["start_dt"], created_at__lt=range_ctx["end_dt"]).aggregate(total=Sum("gross_toman"))["total"] or 0
            if cash_query:
                queryset = queryset.filter(customer__full_name__icontains=cash_query)
        payment_page = Paginator(queryset, payment_page_size).get_page(get_query.get("page", 1))
        payments = payment_page.object_list
        presentation = income_presentation(request.salon, range_ctx, income)
    # Normalized query also keeps links correct when an invalid payment POST
    # renders this template from a different endpoint.
    get_query["tab"] = tab
    get_query["range"] = range_ctx["range_key"]
    get_query["day"] = range_ctx["selected_day"].isoformat()
    if tab in ("income", "cash", "receipts", "reports"):
        get_query["rows"] = str(payment_page_size)
        get_query["page"] = str(payment_page.number)
    debts = open_debts_summary(request.salon) if tab == "debts" else {}
    commissions = commission_day_overview(request.salon, range_ctx["selected_day"]) if tab == "commissions" else None
    commission_query = get_query.get("q", "").strip()[:100] if commissions is not None else ""
    if commission_query:
        def normalize_name(value):
            return " ".join(str(value).translate(str.maketrans("ييك", "ییک")).casefold().split())
        needle = normalize_name(commission_query)
        for key in ("staff_rows", "pending_rows", "settled_rows"):
            commissions[key] = [row for row in commissions[key] if needle in normalize_name(row["staff"].full_display_name)]
        commissions["settled_staff_count"] = len(commissions["settled_rows"])
        commissions["need_payment_staff_count"] = len(commissions["pending_rows"])

    from apps.expenses.forms import ExpenseForm
    from django.utils import timezone
    return {
        **range_ctx,
        "expense_form": ExpenseForm(initial={"expense_date": timezone.localdate()}) if has_permission(membership, P_EXPENSE_MANAGE) and tab in ("cash", "income") else None,
        "expense_modal_open": False,
        "expense_return_url": _finance_return_url(get_query),
        "tab": tab,
        "income": income,
        "dashboard": finance_dashboard(request.salon, range_ctx) if tab in ("income", "cash", "debts", "reports") else None,
        "payments": payments,
        "cash_query": cash_query,
        "cash_partial_total": cash_partial_total,
        "cash_paid_total": cash_paid_total,
        "cash_invoice_total": cash_invoice_total,
        "payment_page": payment_page,
        "payment_page_size": payment_page_size,
        "presentation": presentation,
        "debt_form": debt_form,
        "debt_form_open": debt_form_open,
        **debts,
        "commissions": commissions,
        "commission_query": commission_query,
        "can_manage_debt": can_manage_debt,
        "can_manage_expenses": has_permission(membership, P_EXPENSE_MANAGE),
        "can_settle_commission": can_settle_commission,
        "can_payment_create": can_payment_create,
        "payment_form": payment_form,
        "payment_modal_open": payment_modal_open and can_payment_create and payment_form is not None,
        "payment_return_url": _finance_return_url(get_query),
    }


@salon_required
@require_role(SalonMembership.Role.MANAGER)
def finance_overview(request):
    range_ctx = parse_finance_range(request)
    tab = request.GET.get("tab", "income")
    if tab not in ("income", "cash", "debts", "commissions", "reports", "receipts"):
        tab = "income"

    if request.method == "POST":
        action = request.POST.get("action")
        redirect_params = {
            "tab": tab,
            "range": range_ctx["range_key"],
            "day": range_ctx["selected_day"].isoformat(),
        }
        membership = getattr(request, "membership", None)
        can_manage_debt = has_permission(membership, P_FINANCE_REPORTS)
        can_settle_commission = has_permission(membership, P_COMMISSION_MANAGE)
        if action == "add_debt":
            if not can_manage_debt:
                raise PermissionDenied
            debt_form = SalonDebtForm(request.POST)
            if debt_form.is_valid():
                debt = debt_form.save(commit=False)
                debt.salon = request.salon
                debt.save()
                messages.success(request, "بدهی ثبت شد.")
                redirect_params["tab"] = "debts"
                return redirect(_finance_redirect(**redirect_params))
            query = request.GET.copy()
            query["tab"] = "debts"
            ctx = _finance_overview_context(request, get_query=query, debt_form=debt_form, debt_form_open=True)
            return render(request, "finance/overview.html", ctx)
        elif action == "pay_debt":
            if not can_manage_debt:
                raise PermissionDenied
            debt_id = _positive_pk(request.POST.get("debt_id"))
            debt = get_object_or_404(SalonDebt, pk=debt_id, salon=request.salon)
            pay_form = SalonDebtPaymentForm(request.POST)
            if pay_form.is_valid():
                try:
                    record_salon_debt_payment(
                        salon=request.salon,
                        debt_id=debt.pk,
                        amount_toman=pay_form.cleaned_data["amount_toman"],
                        note=pay_form.cleaned_data.get("note", ""),
                    )
                except ValidationError as exc:
                    msg = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
                    messages.error(request, msg)
                else:
                    messages.success(request, "پرداخت بدهی ثبت شد.")
                    redirect_params["tab"] = "debts"
                    return redirect(_finance_redirect(**redirect_params))
            else:
                messages.error(request, "مبلغ پرداخت بدهی معتبر نیست.")
            query = request.GET.copy()
            query["tab"] = "debts"
            return render(request, "finance/overview.html", _finance_overview_context(request, get_query=query), status=400)
        elif action == "settle_staff":
            if not can_settle_commission:
                raise PermissionDenied
            staff = get_object_or_404(StaffProfile, pk=_positive_pk(request.POST.get("staff_id")), salon=request.salon)
            amount_form = SalonDebtPaymentForm(request.POST)
            if amount_form.is_valid():
                try:
                    create_settlement(request.salon, staff, amount_form.cleaned_data["amount_toman"], amount_form.cleaned_data.get("note", ""))
                except ValidationError as exc:
                    msg = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
                    messages.error(request, msg)
                else:
                    messages.success(request, "تسویه متخصص ثبت شد.")
            else:
                messages.error(request, "مبلغ تسویه معتبر نیست.")
            redirect_params["tab"] = "commissions"
            return redirect(_finance_redirect(**redirect_params))

    payment_modal_open = request.GET.get("payment") == "1"
    ctx = _finance_overview_context(request, payment_modal_open=payment_modal_open)
    return render(request, "finance/overview.html", ctx)


@salon_required
@require_role(SalonMembership.Role.RECEPTIONIST)
def payment_create(request):
    membership = getattr(request, "membership", None)
    if not has_permission(membership, P_PAYMENT_CREATE):
        raise PermissionDenied
    can_view_finance = has_permission(membership, P_FINANCE_REPORTS)
    fallback = reverse("finance:overview") if can_view_finance else reverse("dashboard:home")
    next_url = request.POST.get("next") if request.method == "POST" else request.GET.get("next")
    if (not next_url or not next_url.startswith("/") or next_url.startswith("//")
            or "\\" in next_url or any(ord(c) < 32 for c in next_url)
            or not url_has_allowed_host_and_scheme(next_url, allowed_hosts=set())):
        next_url = fallback
    if _is_finance_overview_path(urlparse(next_url).path) and not can_view_finance:
        next_url = fallback

    if request.method == "GET":
        parts = urlparse(next_url)
        if can_view_finance and _is_finance_overview_path(parts.path):
            return redirect(_append_payment_query(next_url))
        return render(
            request,
            "finance/payment_modal_page.html",
            {
                "payment_form": PaymentForm(salon=request.salon),
                "payment_modal_open": True,
                "payment_return_url": next_url,
            },
        )

    form = PaymentForm(request.POST, salon=request.salon)
    if form.is_valid():
        try:
            record_customer_payment(salon=request.salon, form=form, actor=request.user)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "پرداخت ثبت شد.")
            return redirect(next_url)

    parts = urlparse(next_url)
    if can_view_finance and _is_finance_overview_path(parts.path):
        get_q = _finance_get_from_post(request.POST)
        if not request.POST.get("finance_tab"):
            q = dict(parse_qsl(parts.query, keep_blank_values=True))
            get_q = QueryDict(mutable=True)
            get_q["tab"] = q.get("tab", "income")
            get_q["range"] = q.get("range", "today")
            if q.get("day"):
                get_q["day"] = q["day"]
        ctx = _finance_overview_context(
            request,
            get_query=get_q,
            payment_form=form,
            payment_modal_open=True,
        )
        return render(request, "finance/overview.html", ctx)

    return render(
        request,
        "finance/payment_modal_page.html",
        {
            "payment_form": form,
            "payment_modal_open": True,
            "payment_return_url": next_url,
        },
    )


@salon_required
@require_role(SalonMembership.Role.RECEPTIONIST)
def payment_receipt(request, payment_id):
    if not has_permission(getattr(request, "membership", None), P_PAYMENT_VIEW):
        raise PermissionDenied
    payment = get_object_or_404(Payment.scoped(request.salon).select_related(
        "customer", "appointment__service", "appointment__staff"
    ), pk=payment_id)
    from apps.finance.ledger import payment_refunded
    return render(request, "finance/receipt.html", {"payment": payment,
        "refunds":payment.refunds.filter(salon=request.salon).order_by("-pk"),
        "refund_total":payment_refunded(payment),
        "can_refund":has_permission(getattr(request,"membership",None),P_FINANCE_REPORTS) and payment.status!=Payment.Status.REFUNDED})


@salon_required
@require_role(SalonMembership.Role.MANAGER)
def export_report(request):
    import csv
    from django.http import HttpResponse
    from django.views.decorators.http import require_safe

    if not has_permission(getattr(request,"membership",None),P_FINANCE_REPORTS):
        raise PermissionDenied
    if request.method not in ("GET","HEAD"):
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(["GET","HEAD"])
    span=parse_finance_range(request)
    data=finance_dashboard(request.salon,span)
    response=HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"]="attachment; filename=beautyos-finance.csv"
    response["Cache-Control"]="private, no-store"
    response.write("\ufeff")
    writer=csv.writer(response)
    writer.writerow(["بازه",span["range_display_jalali"]])
    writer.writerow(["شاخص","تومان"])
    for label,key in (("درآمد کل","total_earned"),("درآمد خدمات","earned"),("فروش خالص کالا","product_revenue"),
        ("اجاره جایگاه","rent_total"),("هزینه عمومی","general_expenses"),("بهای مواد","material_total"),
        ("بهای کالای فروش‌رفته","product_cost"),("حقوق","salary_total"),("پورسانت","commission"),
        ("سود عملیاتی برآوردی","operating_estimate"),("دریافتی ناخالص","received"),("استرداد","refunded"),
        ("خالص دریافتی","net_received"),("خرید موجودی","inventory_purchases"),
        ("مطالبات باز فعلی خدمات","receivable_total"),("بدهی باز فعلی","debt_total")):
        writer.writerow([label,data[key]])
    writer.writerow([])
    writer.writerow(["خدمت","تعداد","درآمد","سهم متخصص","مواد","مانده مستقیم"])
    for row in data["service_rows"]:
        # Guard spreadsheet formula injection from user-entered service names.
        name=str(row["name"])
        if name.lstrip().startswith(("=","+","-","@","\t","\r","\n")):
            name="'"+name
        writer.writerow([name,row["count"],row["revenue"],row["commission"],row["materials"],row["contribution"]])
    return response
