from uuid import uuid4

from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.appointments.models import Appointment
from apps.customers.models import Customer
from apps.finance.checkout import MAX_MONEY, appointment_amounts, issue_invoice
from apps.finance.models import Invoice, Payment
from apps.salons.decorators import salon_required
from apps.salons.permissions_policy import P_PAYMENT_CREATE, P_PAYMENT_VIEW, has_permission


class CheckoutForm(forms.Form):
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    voucher = forms.IntegerField(required=False,min_value=1,max_value=MAX_MONEY,label="اعتبار اختصاصی")
    discount = forms.IntegerField(label="تخفیف (تومان)", min_value=0, max_value=MAX_MONEY, required=False)
    cash = forms.IntegerField(label="نقدی (تومان)", min_value=0, max_value=MAX_MONEY, required=False)
    card = forms.IntegerField(label="کارت‌خوان (تومان)", min_value=0, max_value=MAX_MONEY, required=False)
    transfer = forms.IntegerField(label="انتقال بانکی (تومان)", min_value=0, max_value=MAX_MONEY, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.visible_fields():
            field.field.widget.attrs.update({"class": "input-field", "inputmode": "numeric", "placeholder": "۰"})


def _require(request, permission):
    if not has_permission(getattr(request, "membership", None), permission):
        raise PermissionDenied


def _checkout_invoice_context(request):
    """Real, permission-scoped invoice figures shared by both checkout screens."""
    if not has_permission(request.membership, P_PAYMENT_VIEW):
        return {"can_view_invoices": False, "latest_invoices": []}
    invoices = Invoice.scoped(request.salon)
    totals = invoices.filter(created_at__date=timezone.localdate()).aggregate(
        count=Count("pk"),
        customers=Count("customer_id", distinct=True),
        amount=Sum("gross_toman"),
    )
    return {
        "can_view_invoices": True,
        "today_invoice_count": totals["count"] or 0,
        "today_customer_count": totals["customers"] or 0,
        "today_gross_toman": totals["amount"] or 0,
        "latest_invoices": invoices.order_by("-created_at", "-pk")[:3],
    }


@salon_required
@require_http_methods(["GET"])
def checkout_customers(request):
    _require(request, P_PAYMENT_CREATE)
    q = request.GET.get("q", "").strip()[:100]
    customers = Customer.scoped(request.salon).filter(is_deleted=False)
    if q:
        customers = customers.filter(Q(full_name__icontains=q) | Q(phone__icontains=q))
    customers_page = Paginator(customers.order_by("full_name", "pk"), 6).get_page(request.GET.get("page"))
    return render(request, "finance/checkout_customers.html", {
        "customers": customers_page.object_list, "customers_page": customers_page,
        "q": q, **_checkout_invoice_context(request),
    })


@salon_required
@require_http_methods(["GET", "POST"])
def checkout(request, customer_id):
    _require(request, P_PAYMENT_CREATE)
    customer = get_object_or_404(Customer.scoped(request.salon), pk=customer_id, is_deleted=False)
    form = CheckoutForm(request.POST if request.method == "POST" else None, initial={"request_key": uuid4()})
    selected = request.POST.getlist("appointment") if request.method == "POST" else [request.GET.get("appointment", "")]
    if request.method == "POST" and form.is_valid():
        try:
            invoice = issue_invoice(salon=request.salon, customer_id=customer.pk,
                appointment_ids=selected, request_key=form.cleaned_data["request_key"],
                discount=form.cleaned_data["discount"] or 0,
                amounts={method: form.cleaned_data[method] or 0 for method in Payment.Method.values}, actor=request.user,voucher_id=form.cleaned_data["voucher"])
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            return redirect("finance:invoice_detail", invoice_id=invoice.pk)
    appointments = Appointment.scoped(request.salon).filter(customer=customer, status=Appointment.Status.COMPLETED,
        invoice_line__isnull=True, package_use__isnull=True).select_related("service","staff").prefetch_related("payments").order_by("-start_at","-pk")
    rows=[]
    for appt in appointments[:100]:
        gross, paid, discount, owed=appointment_amounts(appt)
        rows.append({"appointment":appt,"gross":gross,"paid":paid,"discount":discount,"owed":owed,"selected":str(appt.pk) in selected})
    from apps.loyalty.benefits import available_vouchers
    return render(request, "finance/checkout.html", {
        "customer": customer, "form": form, "rows": rows,
        "vouchers": available_vouchers(request.salon, customer),
        "selected_voucher": str(form["voucher"].value() or ""),
        **_checkout_invoice_context(request),
    })


@salon_required
@require_http_methods(["GET"])
def invoice_list(request):
    _require(request, P_PAYMENT_VIEW)
    qs = Invoice.scoped(request.salon).order_by("-created_at","-pk")
    page=Paginator(qs, 25).get_page(request.GET.get("page",1))
    return render(request, "finance/invoices.html", {"page":page,
        "can_checkout":has_permission(request.membership,P_PAYMENT_CREATE)})


@salon_required
@require_http_methods(["GET"])
def invoice_detail(request, invoice_id):
    _require(request, P_PAYMENT_VIEW)
    invoice = get_object_or_404(Invoice.scoped(request.salon), pk=invoice_id)
    lines=list(invoice.lines.filter(salon=request.salon).select_related("appointment").prefetch_related("appointment__payments").order_by("pk"))
    current_balance = sum(appointment_amounts(line.appointment)[3] for line in lines
                          if line.appointment.status == Appointment.Status.COMPLETED)
    return render(request, "finance/invoice.html", {
        "invoice": invoice, "lines": lines, "current_balance": current_balance,
        "receipts": invoice.payments.filter(salon=request.salon,paid_amount_toman__gt=0),
        **_checkout_invoice_context(request),
    })
