"""Reception invoice issue: use the existing immutable finance checkout ledger.

The appointment ID and customer are looked up server-side. POST-only and
permission-scoped; no editable customer, amount due, or salon in the payload.
"""
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.appointments.models import Appointment
from apps.finance.checkout import issue_invoice
from apps.finance.checkout_views import CheckoutForm
from apps.finance.models import InvoiceLine, Payment
from apps.salons.decorators import salon_required
from apps.salons.models import SalonMembership
from apps.salons.permissions import require_role
from apps.salons.permissions_policy import P_PAYMENT_CREATE, P_PAYMENT_VIEW, has_permission


def _invoice_url(invoice, *, print_now):
    url = reverse("finance:invoice_detail", kwargs={"invoice_id": invoice.pk})
    return url + ("?print=1" if print_now else "")


@salon_required
@require_role(SalonMembership.Role.RECEPTIONIST)
@require_POST
def issue_from_desk(request, appointment_id):
    if not (
        has_permission(request.membership, P_PAYMENT_CREATE)
        and has_permission(request.membership, P_PAYMENT_VIEW)
    ):
        raise PermissionDenied
    appointment = get_object_or_404(
        Appointment.scoped(request.salon).select_related("customer", "package_use"),
        pk=appointment_id,
    )
    wants_print = request.POST.get("print") == "1"
    # Avoid issuing a second invoice if the receptionist submits the form
    # again from another tab. Finance holds the unique invoice-line invariant.
    previous = InvoiceLine.scoped(request.salon).filter(
        appointment=appointment,
    ).select_related("invoice").first()
    if previous:
        messages.info(request, "فاکتور این نوبت قبلاً ثبت شده است.")
        return redirect(_invoice_url(previous.invoice, print_now=wants_print))
    if appointment.status != Appointment.Status.COMPLETED:
        messages.error(request, "ابتدا خدمت را تکمیل کنید؛ سپس فاکتور صادر کنید.")
        return redirect("appointments:detail", pk=appointment.pk)
    if hasattr(appointment, "package_use"):
        messages.error(request, "این خدمت با پکیج پوشش داده شده و نباید دوباره فاکتور شود.")
        return redirect("appointments:detail", pk=appointment.pk)

    form = CheckoutForm(request.POST)
    if not form.is_valid():
        messages.error(request, "مبالغ یا اطلاعات فاکتور معتبر نیست. فرم را بررسی کنید.")
        return redirect(
            reverse("finance:checkout", args=[appointment.customer_id])
            + "?appointment=" + str(appointment.pk)
        )
    try:
        invoice = issue_invoice(
            salon=request.salon, customer_id=appointment.customer_id,
            appointment_ids=[appointment.pk],
            request_key=form.cleaned_data["request_key"],
            discount=form.cleaned_data.get("discount") or 0,
            amounts={
                method: form.cleaned_data.get(method) or 0
                for method in Payment.Method.values
            },
            actor=request.user,
            voucher_id=form.cleaned_data.get("voucher"),
        )
    except ValidationError as exc:
        messages.error(request, exc.messages[0] if exc.messages else str(exc))
        return redirect(
            reverse("finance:checkout", args=[appointment.customer_id])
            + "?appointment=" + str(appointment.pk)
        )
    messages.success(request, "فاکتور صادر و در پرونده مالی سالن ذخیره شد.")
    return redirect(_invoice_url(invoice, print_now=wants_print))
