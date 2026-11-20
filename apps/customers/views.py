from datetime import time

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from apps.appointments.booking import appointment_booking_context
from apps.appointments.forms import AppointmentForm
from apps.appointments.models import Appointment
from apps.salons.permissions_policy import (
    P_APPOINTMENT_CREATE,
    P_PAYMENT_CREATE,
    has_permission,
)
from apps.services.models import Service
from apps.core.tenant import require_salon_access
from apps.customers.forms import CustomerCreateForm, CustomerForm, CustomerNoteForm
from apps.customers.models import Customer, CustomerActivity, CustomerNote
from apps.customers.queries import filter_customers
from apps.customers.services import log_activity
from apps.finance.models import Payment
from apps.customers.search import search_customers_for_picker
from apps.salons.decorators import salon_required
from apps.salons.models import SalonMembership
from apps.salons.permissions import require_role
from apps.salons.permissions_policy import P_CUSTOMER_VIEW, require_permission

_CUSTOMER_ADVANCED_FIELDS = ("birth_date", "avatar", "is_vip", "marketing_consent")


def _customer_advanced_open(form) -> bool:
    return any(field in form.errors for field in _CUSTOMER_ADVANCED_FIELDS)


def _get_customer(request, pk):
    require_salon_access(request.user, request.salon, SalonMembership.Role.RECEPTIONIST)
    return get_object_or_404(Customer.scoped(request.salon), pk=pk, is_deleted=False)


@salon_required
@require_permission(P_CUSTOMER_VIEW)
def customer_search(request):
    q = request.GET.get("q", "")
    items = search_customers_for_picker(request.salon, q, limit=12)
    return JsonResponse({"results": items})


def _resolve_customers_view_mode(request) -> str:
    view_mode = request.GET.get("view", request.session.get("customers_view", "card"))
    if view_mode in ("card", "table"):
        request.session["customers_view"] = view_mode
    else:
        view_mode = "card"
    return view_mode


def _customer_list_context(
    request,
    *,
    form=None,
    create_modal_open: bool = False,
    advanced_open: bool = False,
):
    q = request.GET.get("q", "").strip()
    segment = request.GET.get("segment", "")
    tag_id = request.GET.get("tag")
    ordering = request.GET.get("sort", "-created")
    view_mode = _resolve_customers_view_mode(request)

    qs = filter_customers(
        request.salon,
        q=q,
        segment=segment,
        tag_id=tag_id,
        ordering=ordering,
    )
    paginator = Paginator(qs, 8 if view_mode == 'card' else 12)
    page = paginator.get_page(request.GET.get("page"))

    from apps.customers.models import CustomerTag

    if form is None:
        form = CustomerCreateForm(salon=request.salon)

    return {
        "page": page,
        "result_count": paginator.count,
        "q": q,
        "segment": segment,
        "tag_id": tag_id,
        "ordering": ordering,
        "view_mode": view_mode,
        "tags": CustomerTag.objects.filter(salon=request.salon),
        "form": form,
        "create_modal_open": create_modal_open,
        "advanced_open": advanced_open,
    }


@salon_required
@require_role(SalonMembership.Role.RECEPTIONIST)
def customer_list(request):
    create_modal_open = request.GET.get("create") == "1"
    ctx = _customer_list_context(request, create_modal_open=create_modal_open)
    return render(request, "customers/list.html", ctx)


@salon_required
@require_role(SalonMembership.Role.RECEPTIONIST)
def customer_create(request):
    if request.method == "GET":
        params = request.GET.copy()
        params.pop("create", None)
        params["create"] = "1"
        return redirect(f"{reverse('customers:list')}?{params.urlencode()}")

    form = CustomerCreateForm(request.POST, request.FILES, salon=request.salon)
    if form.is_valid():
        with transaction.atomic():
            customer = form.save()
            log_activity(
                salon=request.salon,
                customer=customer,
                activity_type=CustomerActivity.ActivityType.CREATED,
                title="مشتری ایجاد شد",
                actor=request.user,
            )
        messages.success(request, "مشتری با موفقیت ثبت شد.")
        return redirect("customers:detail", pk=customer.pk)

    advanced_open = _customer_advanced_open(form)
    ctx = _customer_list_context(
        request,
        form=form,
        create_modal_open=True,
        advanced_open=advanced_open,
    )
    return render(request, "customers/list.html", ctx)


def _customer_appointment_extras(request, *, form=None, customer=None):
    membership = getattr(request, "membership", None)
    can_book = has_permission(membership, P_APPOINTMENT_CREATE)
    can_payment_create = has_permission(membership, P_PAYMENT_CREATE)
    service_prices = {}
    if can_payment_create:
        service_prices = {
            str(s.pk): s.price_toman
            for s in Service.scoped(request.salon).filter(is_active=True, is_deleted=False)
        }
    if form is None and customer is not None and can_book:
        form = AppointmentForm(
            salon=request.salon,
            membership=membership,
            initial={
                "customer": customer,
                "appointment_date": timezone.localdate(),
                "appointment_time": time(9, 0),
            },
        )
    return {
        "appointment_form": form,
        "can_payment_create": can_payment_create,
        "service_prices": service_prices,
        "can_book_appointment": can_book,
    }


def _customer_detail_context(
    request,
    customer,
    *,
    note_form=None,
    edit_form=None,
    edit_modal_open: bool = False,
    book_modal_open: bool = False,
    appointment_form=None,
):
    if note_form is None:
        note_form = CustomerNoteForm()
    if edit_form is None:
        edit_form = CustomerForm(instance=customer, salon=request.salon)

    upcoming = (
        Appointment.scoped(request.salon)
        .filter(
            customer=customer,
            start_at__gte=timezone.now(),
            status__in=[Appointment.Status.PENDING, Appointment.Status.CONFIRMED, Appointment.Status.CHECKED_IN],
        )
        .select_related("service", "staff")
        .order_by("start_at")[:10]
    )
    history = (
        Appointment.scoped(request.salon)
        .filter(customer=customer)
        .select_related("service", "staff")
        .order_by("-start_at")[:20]
    )
    payments = Payment.scoped(request.salon).filter(customer=customer).order_by("-created_at")[:15]
    activities = customer.activities.select_related("actor").order_by("-created_at")[:50]
    recent_notes = customer.notes.select_related("author").order_by("-created_at")[:20]

    appt_extra = {}
    if has_permission(request.membership, P_APPOINTMENT_CREATE):
        if appointment_form is None and (book_modal_open or request.GET.get("book") == "1"):
            appointment_form = AppointmentForm(
                salon=request.salon,
                membership=request.membership,
                initial={
                    "customer": customer,
                    "appointment_date": timezone.localdate(),
                    "appointment_time": time(9, 0),
                },
            )
        if appointment_form is not None or book_modal_open:
            appt_extra = appointment_booking_context(
                request,
                form=appointment_form,
                book_modal_open=book_modal_open,
                customer_locked=customer,
            )
            appt_extra["from_customer_detail"] = customer.pk
        else:
            appt_extra["can_book_appointment"] = True

    return {
        "customer": customer,
        "note_form": note_form,
        "upcoming": upcoming,
        "history": history,
        "payments": payments,
        "activities": activities,
        "recent_notes": recent_notes,
        "edit_form": edit_form,
        "edit_modal_open": edit_modal_open,
        "book_modal_open": book_modal_open,
        **appt_extra,
    }


@salon_required
@require_role(SalonMembership.Role.RECEPTIONIST)
def customer_edit(request, pk):
    customer = _get_customer(request, pk)
    if request.method == "GET":
        return redirect(f"{reverse('customers:detail', kwargs={'pk': pk})}?edit=1")

    form = CustomerForm(request.POST, request.FILES, instance=customer, salon=request.salon)
    if form.is_valid():
        form.save()
        log_activity(
            salon=request.salon,
            customer=customer,
            activity_type=CustomerActivity.ActivityType.UPDATED,
            title="اطلاعات مشتری ویرایش شد",
            actor=request.user,
        )
        messages.success(request, "تغییرات ذخیره شد.")
        return redirect("customers:detail", pk=customer.pk)

    ctx = _customer_detail_context(request, customer, edit_form=form, edit_modal_open=True)
    return render(request, "customers/detail.html", ctx)


@salon_required
@require_role(SalonMembership.Role.RECEPTIONIST)
def customer_detail(request, pk):
    customer = _get_customer(request, pk)
    edit_modal_open = request.GET.get("edit") == "1"
    book_modal_open = request.GET.get("book") == "1"
    ctx = _customer_detail_context(
        request,
        customer,
        edit_modal_open=edit_modal_open,
        book_modal_open=book_modal_open,
    )
    return render(request, "customers/detail.html", ctx)


@salon_required
@require_role(SalonMembership.Role.RECEPTIONIST)
def customer_add_note(request, pk):
    customer = _get_customer(request, pk)
    if request.method != "POST":
        raise PermissionDenied
    form = CustomerNoteForm(request.POST)
    if form.is_valid():
        note = form.save(commit=False)
        note.salon = request.salon
        note.customer = customer
        note.author = request.user
        note.save()
        Customer.objects.filter(pk=customer.pk).update(notes_count=customer.notes.count())
        log_activity(
            salon=request.salon,
            customer=customer,
            activity_type=CustomerActivity.ActivityType.NOTE,
            title="یادداشت جدید",
            description=note.body[:200],
            actor=request.user,
            entity_type="note",
            entity_id=str(note.pk),
        )
        messages.success(request, "یادداشت ثبت شد.")
    return redirect("customers:detail", pk=pk)


@salon_required
@require_role(SalonMembership.Role.MANAGER)
def customer_archive(request, pk):
    customer = _get_customer(request, pk)
    if request.method == "POST":
        customer.is_deleted = True
        customer.deleted_at = timezone.now()
        customer.save(update_fields=["is_deleted", "deleted_at", "updated_at"])
        log_activity(
            salon=request.salon,
            customer=customer,
            activity_type=CustomerActivity.ActivityType.ARCHIVED,
            title="مشتری آرشیو شد",
            actor=request.user,
        )
        messages.success(request, "مشتری آرشیو شد.")
        return redirect("customers:list")
    return render(request, "customers/confirm_archive.html", {"customer": customer})
