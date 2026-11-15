from django.contrib import messages
from django.db.models import Max
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.salons.decorators import salon_required
from apps.salons.models import SalonMembership
from apps.salons.permissions import require_role
from apps.services.forms import ServiceCategoryQuickForm, ServiceCreateForm, ServiceForm
from apps.services.models import Service

_ADVANCED_SERVICE_FIELDS = ("is_active", "is_public", "image", "duration_minutes", "sort_order")


def _service_advanced_open(form) -> bool:
    return any(field in form.errors for field in _ADVANCED_SERVICE_FIELDS)


def _next_service_sort_order(salon) -> int:
    current = Service.scoped(salon).filter(is_deleted=False).aggregate(m=Max("sort_order"))["m"]
    if current is None:
        return 0
    return current + 1


def _service_list_context(
    request,
    *,
    form=None,
    create_modal_open: bool = False,
    category_panel_open: bool = False,
    category_error: str = "",
    new_category_name: str = "",
    advanced_open: bool = False,
    edit_form=None,
    edit_service=None,
    edit_modal_open: bool = False,
    edit_category_panel_open: bool = False,
    edit_category_error: str = "",
    edit_new_category_name: str = "",
    edit_advanced_open: bool = False,
):
    services = Service.scoped(request.salon).filter(is_deleted=False).select_related("category")
    if form is None:
        form = ServiceCreateForm(salon=request.salon)
    return {
        "services": services,
        "form": form,
        "create_modal_open": create_modal_open,
        "category_panel_open": category_panel_open,
        "category_error": category_error,
        "new_category_name": new_category_name,
        "advanced_open": advanced_open,
        "edit_form": edit_form,
        "edit_service": edit_service,
        "edit_modal_open": edit_modal_open,
        "edit_category_panel_open": edit_category_panel_open,
        "edit_category_error": edit_category_error,
        "edit_new_category_name": edit_new_category_name,
        "edit_advanced_open": edit_advanced_open,
    }


def _handle_service_create_post(request):
    category_panel_open = False
    category_error = ""
    new_category_name = ""
    advanced_open = False
    intent = request.POST.get("intent", "save_service")

    if intent == "add_category":
        new_category_name = (request.POST.get("new_category_name") or "").strip()
        category_panel_open = True
        cat_form = ServiceCategoryQuickForm({"name": new_category_name}, salon=request.salon)
        service_form = ServiceCreateForm(request.POST, request.FILES, salon=request.salon)
        if cat_form.is_valid():
            category = cat_form.save()
            data = request.POST.copy()
            data["category"] = str(category.pk)
            service_form = ServiceCreateForm(data, request.FILES, salon=request.salon)
            category_panel_open = False
            new_category_name = ""
            messages.success(request, "دسته‌بندی اضافه شد.")
        else:
            if cat_form.errors.get("name"):
                category_error = cat_form.errors["name"][0]
            service_form = ServiceCreateForm(request.POST, request.FILES, salon=request.salon)
            advanced_open = _service_advanced_open(service_form)
        return False, service_form, category_panel_open, category_error, new_category_name, advanced_open

    service_form = ServiceCreateForm(request.POST, request.FILES, salon=request.salon)
    advanced_open = _service_advanced_open(service_form)
    if service_form.is_valid():
        obj = service_form.save(commit=False)
        obj.salon = request.salon
        obj.duration_minutes = obj.duration_minutes or 30
        obj.sort_order = _next_service_sort_order(request.salon)
        obj.save()
        messages.success(request, "خدمت ثبت شد.")
        return True, service_form, category_panel_open, category_error, new_category_name, advanced_open

    return False, service_form, category_panel_open, category_error, new_category_name, advanced_open


def _handle_service_edit_post(request, service):
    category_panel_open = False
    category_error = ""
    new_category_name = ""
    advanced_open = False
    intent = request.POST.get("intent", "save_service")

    if intent == "add_category":
        new_category_name = (request.POST.get("new_category_name") or "").strip()
        category_panel_open = True
        cat_form = ServiceCategoryQuickForm({"name": new_category_name}, salon=request.salon)
        edit_form = ServiceForm(request.POST, request.FILES, instance=service, salon=request.salon)
        if cat_form.is_valid():
            category = cat_form.save()
            data = request.POST.copy()
            data["category"] = str(category.pk)
            edit_form = ServiceForm(data, request.FILES, instance=service, salon=request.salon)
            category_panel_open = False
            new_category_name = ""
            messages.success(request, "دسته‌بندی اضافه شد.")
        else:
            if cat_form.errors.get("name"):
                category_error = cat_form.errors["name"][0]
            advanced_open = _service_advanced_open(edit_form)
        return False, edit_form, category_panel_open, category_error, new_category_name, advanced_open

    edit_form = ServiceForm(request.POST, request.FILES, instance=service, salon=request.salon)
    advanced_open = _service_advanced_open(edit_form)
    if edit_form.is_valid():
        edit_form.save()
        messages.success(request, "خدمت به‌روزرسانی شد.")
        return True, edit_form, category_panel_open, category_error, new_category_name, advanced_open

    return False, edit_form, category_panel_open, category_error, new_category_name, advanced_open


@salon_required
@require_role(SalonMembership.Role.MANAGER)
def service_list(request):
    create_modal_open = request.GET.get("create") == "1"
    edit_modal_open = False
    edit_form = None
    edit_service = None
    edit_pk = request.GET.get("edit")
    if edit_pk:
        edit_service = get_object_or_404(Service.scoped(request.salon), pk=edit_pk, is_deleted=False)
        edit_form = ServiceForm(instance=edit_service, salon=request.salon)
        edit_modal_open = True
    ctx = _service_list_context(
        request,
        create_modal_open=create_modal_open,
        edit_form=edit_form,
        edit_service=edit_service,
        edit_modal_open=edit_modal_open,
    )
    return render(request, "services/list.html", ctx)


@salon_required
@require_role(SalonMembership.Role.MANAGER)
def service_create(request):
    if request.method == "GET":
        params = request.GET.copy()
        params.pop("create", None)
        params["create"] = "1"
        return redirect(f"{reverse('services:list')}?{params.urlencode()}")

    ok, service_form, category_panel_open, category_error, new_category_name, advanced_open = (
        _handle_service_create_post(request)
    )
    if ok:
        return redirect("services:list")

    ctx = _service_list_context(
        request,
        form=service_form,
        create_modal_open=True,
        category_panel_open=category_panel_open,
        category_error=category_error,
        new_category_name=new_category_name,
        advanced_open=advanced_open,
    )
    return render(request, "services/list.html", ctx)


@salon_required
@require_role(SalonMembership.Role.MANAGER)
def service_edit(request, pk):
    service = get_object_or_404(Service.scoped(request.salon), pk=pk, is_deleted=False)
    if request.method == "GET":
        return redirect(f"{reverse('services:list')}?edit={pk}")

    ok, edit_form, category_panel_open, category_error, new_category_name, advanced_open = _handle_service_edit_post(
        request, service
    )
    if ok:
        return redirect("services:list")

    ctx = _service_list_context(
        request,
        edit_form=edit_form,
        edit_service=service,
        edit_modal_open=True,
        edit_category_panel_open=category_panel_open,
        edit_category_error=category_error,
        edit_new_category_name=new_category_name,
        edit_advanced_open=advanced_open,
    )
    return render(request, "services/list.html", ctx)
