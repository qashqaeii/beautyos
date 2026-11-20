from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from apps.portfolio.forms import PortfolioItemForm
from apps.portfolio.models import PortfolioItem
from apps.salons.decorators import salon_required
from apps.salons.models import SalonMembership
from apps.salons.permissions import require_role


@salon_required
@require_role(SalonMembership.Role.MANAGER)
def portfolio_list(request):
    items = PortfolioItem.scoped(request.salon).filter(is_deleted=False).order_by("sort_order", "-created_at")
    pager = Paginator(items, 6).get_page(request.GET.get("page"))
    return render(request, "portfolio/list.html", {"items": pager.object_list, "portfolio_page": pager})


@salon_required
@require_role(SalonMembership.Role.MANAGER)
def portfolio_create(request):
    if request.method == "POST":
        form = PortfolioItemForm(request.POST, request.FILES, salon=request.salon)
        if form.is_valid():
            item = form.save(commit=False)
            item.salon = request.salon
            item.save()
            messages.success(request, "نمونه‌کار منتشر شد.")
            return redirect("portfolio:list")
    else:
        form = PortfolioItemForm(salon=request.salon)
    return render(request, "portfolio/form.html", {"form": form})


@salon_required
@require_role(SalonMembership.Role.MANAGER)
def portfolio_edit(request, pk):
    item = get_object_or_404(PortfolioItem.scoped(request.salon), pk=pk, is_deleted=False)
    if request.method == "POST":
        form = PortfolioItemForm(request.POST, request.FILES, instance=item, salon=request.salon)
        if form.is_valid():
            form.save()
            messages.success(request, "به‌روزرسانی شد.")
            return redirect("portfolio:list")
    else:
        form = PortfolioItemForm(instance=item, salon=request.salon)
    return render(request, "portfolio/form.html", {"form": form, "item": item})
