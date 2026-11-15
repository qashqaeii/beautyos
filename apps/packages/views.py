from django.contrib import messages
from django.shortcuts import redirect, render

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
        return redirect("packages:list")
    return render(request, "packages/sell.html", {"form": form})
