from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.appointments.models import Appointment
from apps.packages.services import consume_package_session
from apps.salons.permissions_policy import P_PACKAGE_MANAGE, require_permission

from apps.packages.forms import SellPackageForm, ServicePackageForm
from apps.packages.models import CustomerPackage, ServicePackage
from apps.salons.decorators import salon_required
from apps.salons.models import SalonMembership
from apps.salons.permissions import require_role


@salon_required
@require_role(SalonMembership.Role.MANAGER)
def package_list(request):
    packages = ServicePackage.scoped(request.salon).order_by("name")
    sales = CustomerPackage.scoped(request.salon).select_related("customer", "package").order_by("-purchased_at")[:20]
    return render(request, "packages/list.html", {"packages": packages, "sales": sales})


@salon_required
@require_role(SalonMembership.Role.MANAGER)
def package_create(request):
    form = ServicePackageForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        pkg = form.save(commit=False)
        pkg.salon = request.salon
        pkg.save()
        messages.success(request, "پکیج ایجاد شد.")
        return redirect("packages:list")
    return render(request, "packages/form.html", {"form": form})


@salon_required
@require_role(SalonMembership.Role.RECEPTIONIST)
def sell(request):
    form = SellPackageForm(request.POST or None, salon=request.salon)
    if request.method == "POST" and form.is_valid():
        form.save(request.salon)
        messages.success(request, "پکیج برای مشتری ثبت شد.")
        if request.membership.role == SalonMembership.Role.RECEPTIONIST:
            return redirect("packages:sell")
        return redirect("packages:list")
    return render(request, "packages/sell.html", {"form": form})


@salon_required
@require_permission(P_PACKAGE_MANAGE)
@require_http_methods(["POST"])
def use_session(request, appointment_id):
    """Apply one prepaid session to this customer's completed visit."""
    appointment = get_object_or_404(
        Appointment.scoped(request.salon), pk=appointment_id,
    )
    try:
        package_id = int(request.POST.get("customer_package", ""))
        if package_id <= 0:
            raise ValueError
    except (TypeError, ValueError):
        messages.error(request, "پکیج معتبری برای این مشتری انتخاب کنید.")
        return redirect("appointments:detail", pk=appointment.pk)
    purchase = get_object_or_404(
        CustomerPackage.scoped(request.salon),
        pk=package_id, customer_id=appointment.customer_id,
    )
    try:
        consume_package_session(purchase, appointment, actor=request.user)
    except ValidationError as exc:
        messages.error(request, exc.messages[0] if exc.messages else str(exc))
    else:
        messages.success(request, "یک جلسه از پکیج مشتری کسر شد؛ این خدمت دوباره در صندوق محاسبه نمی‌شود.")
    return redirect("appointments:detail", pk=appointment.pk)
