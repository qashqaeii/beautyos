from django.contrib import messages
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.inventory.forms import (
    INVENTORY_CATEGORY_PRESETS,
    InventoryCategoryForm,
    InventoryCategoryQuickForm,
    InventoryItemCreateForm,
    StockQuantityForm,
    inventory_category_queryset,
)
from apps.inventory.models import InventoryCategory, InventoryItem, StockMovement
from apps.inventory.services import apply_movement, create_inventory_item
from apps.salons.decorators import salon_required
from apps.salons.permissions_policy import P_INVENTORY_MANAGE, require_permission


def _inventory_list_queryset(salon, *, query: str, category_key: str):
    qs = InventoryItem.scoped(salon).select_related("category").order_by("name")
    if query:
        qs = qs.filter(name__icontains=query)
    if category_key == "none":
        qs = qs.filter(category__isnull=True)
    elif category_key.isdigit():
        qs = qs.filter(category_id=int(category_key))
    return qs


def _inventory_list_context(
    request,
    *,
    item_form=None,
    create_modal_open: bool = False,
    category_panel_open: bool = False,
    category_error: str = "",
    new_category_name: str = "",
):
    query = (request.GET.get("q") or "").strip()
    category_key = request.GET.get("category", "")
    categories = inventory_category_queryset(request.salon)
    items = list(_inventory_list_queryset(request.salon, query=query, category_key=category_key))
    low_count = sum(1 for i in items if i.is_low_stock or i.is_out_of_stock)
    pager = Paginator(items, 12).get_page(request.GET.get("page"))
    if item_form is None:
        item_form = InventoryItemCreateForm(salon=request.salon)
    return {
        "items": pager.object_list, "inventory_page": pager,
        "categories": categories,
        "query": query,
        "category_key": category_key,
        "low_count": low_count,
        "form": item_form,
        "create_modal_open": create_modal_open,
        "category_panel_open": category_panel_open,
        "category_error": category_error,
        "new_category_name": new_category_name,
    }


def _handle_item_create_post(request):
    category_panel_open = False
    category_error = ""
    new_category_name = ""
    intent = request.POST.get("intent", "save_item")

    if intent == "add_category":
        new_category_name = (request.POST.get("new_category_name") or "").strip()
        category_panel_open = True
        cat_form = InventoryCategoryQuickForm({"name": new_category_name}, salon=request.salon)
        item_form = InventoryItemCreateForm(request.POST, salon=request.salon)
        if cat_form.is_valid():
            category = cat_form.save()
            data = request.POST.copy()
            data["category"] = str(category.pk)
            item_form = InventoryItemCreateForm(data, salon=request.salon)
            category_panel_open = False
            new_category_name = ""
            messages.success(request, "دسته‌بندی اضافه شد.")
        elif cat_form.errors.get("name"):
            category_error = cat_form.errors["name"][0]
        return False, item_form, category_panel_open, category_error, new_category_name

    item_form = InventoryItemCreateForm(request.POST, salon=request.salon)
    if item_form.is_valid():
        data = item_form.cleaned_data
        create_inventory_item(
            salon=request.salon,
            name=data["inventory_product_name"],
            unit=data["unit"],
            minimum_quantity=data["minimum_quantity"] or 0,
            category=data.get("category"),
            initial_quantity=data.get("initial_quantity") or 0,
        )
        messages.success(request, "محصول ثبت شد.")
        return True, item_form, category_panel_open, category_error, new_category_name

    return False, item_form, category_panel_open, category_error, new_category_name


@salon_required
@require_permission(P_INVENTORY_MANAGE)
def list_items(request):
    create_modal_open = request.GET.get("create") == "1"
    ctx = _inventory_list_context(request, create_modal_open=create_modal_open)
    return render(request, "inventory/list.html", ctx)


@salon_required
@require_permission(P_INVENTORY_MANAGE)
def item_create(request):
    if request.method == "GET":
        params = request.GET.copy()
        params.pop("create", None)
        params["create"] = "1"
        return redirect(f"{reverse('inventory:list')}?{params.urlencode()}")

    ok, item_form, category_panel_open, category_error, new_category_name = _handle_item_create_post(request)
    if ok:
        return redirect("inventory:list")

    ctx = _inventory_list_context(
        request,
        item_form=item_form,
        create_modal_open=True,
        category_panel_open=category_panel_open,
        category_error=category_error,
        new_category_name=new_category_name,
    )
    return render(request, "inventory/list.html", ctx)


@salon_required
@require_permission(P_INVENTORY_MANAGE)
def categories_manage(request):
    if request.method == "POST":
        if request.POST.get("intent") == "create":
            form = InventoryCategoryQuickForm({"name": request.POST.get("name", "")}, salon=request.salon)
            if form.is_valid():
                form.save()
                messages.success(request, "دسته‌بندی اضافه شد.")
                return redirect("inventory:categories")
            messages.error(request, form.errors.get("name", ["خطا در ثبت دسته"])[0])
        elif request.POST.get("intent") == "edit":
            pk = request.POST.get("category_id")
            category = get_object_or_404(InventoryCategory.scoped(request.salon), pk=pk)
            form = InventoryCategoryForm(request.POST, instance=category)
            if form.is_valid():
                form.save()
                messages.success(request, "نام دسته به‌روزرسانی شد.")
                return redirect("inventory:categories")

    categories = inventory_category_queryset(request.salon)
    uncategorized_count = InventoryItem.scoped(request.salon).filter(category__isnull=True).count()

    return render(
        request,
        "inventory/categories.html",
        {
            "categories": categories,
            "uncategorized_count": uncategorized_count,
            "category_presets": INVENTORY_CATEGORY_PRESETS,
        },
    )


@salon_required
@require_permission(P_INVENTORY_MANAGE)
def stock_in(request, pk):
    item = get_object_or_404(InventoryItem.scoped(request.salon), pk=pk)
    if request.method == "POST":
        form = StockQuantityForm(request.POST)
    else:
        form = StockQuantityForm()
    if request.method == "POST" and form.is_valid():
        apply_movement(
            salon=request.salon,
            item=item,
            kind=StockMovement.Kind.IN,
            quantity=form.cleaned_data["quantity"],
            note=form.cleaned_data.get("note", ""),
        )
        messages.success(request, "ورود موجودی ثبت شد.")
        return redirect("inventory:list")
    return render(
        request,
        "inventory/stock_form.html",
        {
            "item": item,
            "form": form,
            "kind": "in",
            "page_title": "ثبت ورود موجودی",
            "submit_label": "ثبت ورود",
        },
    )


@salon_required
@require_permission(P_INVENTORY_MANAGE)
def stock_out(request, pk):
    item = get_object_or_404(InventoryItem.scoped(request.salon), pk=pk)
    if request.method == "POST":
        form = StockQuantityForm(request.POST)
    else:
        form = StockQuantityForm()
    if request.method == "POST" and form.is_valid():
        try:
            apply_movement(
                salon=request.salon,
                item=item,
                kind=StockMovement.Kind.OUT,
                quantity=form.cleaned_data["quantity"],
                note=form.cleaned_data.get("note", ""),
            )
            messages.success(request, "مصرف موجودی ثبت شد.")
            return redirect("inventory:list")
        except ValidationError as exc:
            msg = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
            messages.error(request, msg)
    return render(
        request,
        "inventory/stock_form.html",
        {
            "item": item,
            "form": form,
            "kind": "out",
            "page_title": "ثبت مصرف موجودی",
            "submit_label": "ثبت مصرف",
        },
    )
