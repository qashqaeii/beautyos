"""Private platform control center: no salon middleware context is required for operators.

No salon/customer data is written from the overview, lists or reporting pages.
Sensitive mutations are POST-only, CSRF protected and audited.
"""
from datetime import datetime, time, timedelta

import jdatetime
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts.models import User
from apps.appointments.models import Appointment
from apps.audit.models import AuditLog
from apps.customers.models import Customer
from apps.expenses.models import Expense
from apps.finance.models import Payment
from apps.platform_admin.forms import ArticleForm, MessageForm, TicketForm
from apps.platform_admin.command_center import command_center_snapshot
from apps.platform_admin.guards import platform_required
from apps.platform_admin.models import SupportMessage, SupportTicket, SalonSubscription, PlatformActivityEvent
from apps.salons.decorators import salon_required
from apps.salons.models import Salon, SalonMembership
from apps.salons.permissions_policy import P_SALON_SETTINGS, require_permission
from apps.services.models import Service
from apps.staff.models import StaffProfile
from apps.website.models import BlogPost, ContactInquiry


def _last_days(request, default=30):
    try:
        value = int(request.GET.get("days", default))
    except (TypeError, ValueError):
        value = default
    return value if value in (7, 30, 90) else default


def _page(request, queryset, size=20):
    return Paginator(queryset, size).get_page(request.GET.get("page"))


def _audit(request, action, entity_type, entity_id, message, salon=None):
    AuditLog.objects.create(
        actor=request.user, salon=salon, action=action,
        entity_type=entity_type, entity_id=str(entity_id),
        message=message, metadata={"scope": "platform"},
        ip_address=request.META.get("REMOTE_ADDR") or None,
    )


def _stats(days):
    now = timezone.now()
    since = now - timedelta(days=days)
    receipts = (
        Payment.objects.filter(created_at__gte=since, paid_amount_toman__gt=0)
        .exclude(status=Payment.Status.REFUNDED)
        .aggregate(total=Sum("paid_amount_toman"))
    )["total"] or 0
    return {
        "salons_total": Salon.objects.count(),
        "salons_active": Salon.objects.filter(is_active=True).count(),
        "salons_recent": Salon.objects.filter(created_at__gte=since).count(),
        "salons_pending_setup": Salon.objects.filter(settings__onboarding_completed_at__isnull=True).count(),
        "users_total": User.objects.count(),
        "users_recent": User.objects.filter(created_at__gte=since).count(),
        "bookings_count": Appointment.objects.filter(created_at__gte=since).count(),
        "bookings_public": Appointment.objects.filter(
            created_at__gte=since, source=Appointment.Source.PUBLIC
        ).count(),
        "appointments_completed": Appointment.objects.filter(
            created_at__gte=since, status=Appointment.Status.COMPLETED
        ).count(),
        "salon_receipts_toman": int(receipts),
        "tickets_open": SupportTicket.objects.filter(
            status__in=[SupportTicket.Status.OPEN, SupportTicket.Status.IN_PROGRESS]
        ).count(),
        "posts_published": BlogPost.published_qs().count(),
    }


def _owner_name(salon):
    membership = (
        SalonMembership.objects.filter(salon=salon, role=SalonMembership.Role.OWNER, is_active=True)
        .select_related("user").order_by("created_at").first()
    )
    return membership.user if membership else None


@platform_required
def overview(request):
    days = _last_days(request)
    return render(request, "platform_admin/overview.html", {
        "days": days,
        "command": command_center_snapshot(days=days),
        "kpis": _stats(days),
        "latest_salons": Salon.objects.order_by("-created_at")[:6],
        "latest_tickets": SupportTicket.objects.select_related("salon").order_by("-last_activity_at")[:6],
        "recent_audit": AuditLog.objects.select_related("salon", "actor").order_by("-created_at")[:7],
    })


@platform_required
def salons(request):
    q = (request.GET.get("q") or "").strip()[:80]
    status = (request.GET.get("status") or "").strip()
    qs = Salon.objects.select_related("settings").annotate(
        owners_count=Count(
            "memberships", filter=Q(memberships__role=SalonMembership.Role.OWNER,
                                   memberships__is_active=True), distinct=True,
        ),
        members_count=Count("memberships", distinct=True),
    )
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(slug__icontains=q) |
                       Q(city__icontains=q) | Q(public_phone__icontains=q))
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "inactive":
        qs = qs.filter(is_active=False)
    elif status == "setup":
        qs = qs.filter(settings__onboarding_completed_at__isnull=True)
    else:
        status = ""
    return render(request, "platform_admin/salons.html", {
        "page": _page(request, qs.order_by("-created_at", "pk")),
        "q": q, "status": status,
    })


@platform_required
def salon_detail(request, salon_id):
    salon = get_object_or_404(Salon.objects.select_related("settings"), pk=salon_id)
    members = SalonMembership.objects.filter(salon=salon).select_related("user").order_by("role", "user__full_name")
    gross = (
        Payment.objects.filter(salon=salon, paid_amount_toman__gt=0)
        .exclude(status=Payment.Status.REFUNDED)
        .aggregate(total=Sum("paid_amount_toman"))["total"] or 0
    )
    expenses = Expense.objects.filter(salon=salon).aggregate(total=Sum("amount_toman"))["total"] or 0
    now = timezone.now()
    activity_since = now - timedelta(days=30)
    prior_since = activity_since - timedelta(days=30)
    recent_activity = PlatformActivityEvent.objects.filter(
        salon=salon, occurred_at__gte=activity_since, occurred_at__lt=now,
    )
    previous_activity = PlatformActivityEvent.objects.filter(
        salon=salon, occurred_at__gte=prior_since, occurred_at__lt=activity_since,
    )
    activity_breakdown = list(recent_activity.values("kind").annotate(
        total=Sum("count"),
    ).order_by("-total"))
    kind_labels = dict(PlatformActivityEvent.Kind.choices)
    for item in activity_breakdown:
        item["label"] = kind_labels.get(item["kind"], item["kind"])
    subscription = SalonSubscription.objects.filter(salon=salon).select_related("plan").first()
    return render(request, "platform_admin/salon_detail.html", {
        "salon": salon,
        "subscription": subscription,
        "activity_current": recent_activity.aggregate(total=Sum("count"))["total"] or 0,
        "activity_previous": previous_activity.aggregate(total=Sum("count"))["total"] or 0,
        "activity_breakdown": activity_breakdown,
        "activity_latest": recent_activity.order_by("-occurred_at")[:8],
        "members": members,
        "metrics": {
            "customers": Customer.objects.filter(salon=salon, is_deleted=False).count(),
            "services": Service.objects.filter(salon=salon, is_deleted=False).count(),
            "specialists": StaffProfile.objects.filter(salon=salon, is_deleted=False).count(),
            "bookings": Appointment.objects.filter(salon=salon).count(),
            "online_bookings": Appointment.objects.filter(salon=salon, source=Appointment.Source.PUBLIC).count(),
            "receipts": int(gross), "expenses": int(expenses),
        },
        "tickets": SupportTicket.objects.filter(salon=salon)[:5],
        "audit_logs": AuditLog.objects.filter(salon=salon).select_related("actor").order_by("-created_at")[:12],
    })


@platform_required
@require_POST
def salon_status(request, salon_id):
    action = request.POST.get("action")
    reason = (request.POST.get("reason") or "").strip()[:500]
    if action not in ("activate", "deactivate") or len(reason) < 8:
        messages.error(request, "برای تغییر وضعیت، اقدام معتبر و دلیل حداقل ۸ کاراکتری لازم است.")
        return redirect("platform_admin:salon_detail", salon_id=salon_id)
    with transaction.atomic():
        salon = get_object_or_404(Salon.objects.select_for_update(), pk=salon_id)
        new_value = action == "activate"
        if salon.is_active != new_value:
            salon.is_active = new_value
            salon.save(update_fields=["is_active", "updated_at"])
            _audit(request, AuditLog.Action.SECURITY, "platform_salon_status",
                   salon.pk, f"وضعیت سالن به {'فعال' if new_value else 'غیرفعال'} تغییر یافت: {reason}", salon)
    messages.success(request, "وضعیت سالن ثبت شد. وضعیت رزرو آنلاین به‌صورت خودکار تغییر نمی‌کند.")
    return redirect("platform_admin:salon_detail", salon_id=salon_id)


@platform_required
def users(request):
    q = (request.GET.get("q") or "").strip()[:80]
    status = request.GET.get("status", "")
    qs = User.objects.annotate(salons_count=Count("salon_memberships", distinct=True))
    if q:
        qs = qs.filter(Q(phone__icontains=q) | Q(full_name__icontains=q))
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "inactive":
        qs = qs.filter(is_active=False)
    elif status == "operators":
        qs = qs.filter(is_superuser=True)
    else:
        status = ""
    return render(request, "platform_admin/users.html", {
        "page": _page(request, qs.order_by("-created_at", "pk")),
        "q": q, "status": status,
    })


@platform_required
def user_detail(request, user_id):
    person = get_object_or_404(User, pk=user_id)
    memberships = SalonMembership.objects.filter(user=person).select_related("salon").order_by("-created_at")
    recent_events = AuditLog.objects.filter(actor=person).select_related("salon").order_by("-created_at")[:20]
    return render(request, "platform_admin/user_detail.html", {
        "person": person, "memberships": memberships, "events": recent_events,
    })


@platform_required
@require_POST
def user_status(request, user_id):
    action = request.POST.get("action")
    reason = (request.POST.get("reason") or "").strip()[:500]
    if action not in ("activate", "deactivate") or len(reason) < 8:
        messages.error(request, "اقدام معتبر و دلیل حداقل ۸ کاراکتری لازم است.")
        return redirect("platform_admin:user_detail", user_id=user_id)
    with transaction.atomic():
        person = get_object_or_404(User.objects.select_for_update(), pk=user_id)
        if person.is_superuser or person.pk == request.user.pk:
            raise PermissionDenied("ویرایش وضعیت مدیران مرکزی از این صفحه مجاز نیست.")
        next_state = action == "activate"
        if person.is_active != next_state:
            person.is_active = next_state
            person.save(update_fields=["is_active", "updated_at"])
            _audit(request, AuditLog.Action.SECURITY, "platform_user_status", person.pk,
                   f"وضعیت کاربر به {'فعال' if next_state else 'غیرفعال'} تغییر یافت: {reason}")
    messages.success(request, "وضعیت کاربر به‌روزرسانی شد.")
    return redirect("platform_admin:user_detail", user_id=user_id)


@platform_required
def reports(request):
    days = _last_days(request, 90)
    base = _stats(days)
    months = []
    jalali_now = jdatetime.date.fromgregorian(date=timezone.localdate())
    year, month = jalali_now.year, jalali_now.month
    for index in range(5, -1, -1):
        y, m = year, month - index
        while m < 1:
            y -= 1
            m += 12
        start = jdatetime.date(y, m, 1).togregorian()
        next_y, next_m = (y + 1, 1) if m == 12 else (y, m + 1)
        stop = jdatetime.date(next_y, next_m, 1).togregorian()
        aware_start = timezone.make_aware(datetime.combine(start, time.min))
        aware_end = timezone.make_aware(datetime.combine(stop, time.min))
        received = (Payment.objects.filter(
            created_at__gte=aware_start, created_at__lt=aware_end, paid_amount_toman__gt=0,
        ).exclude(status=Payment.Status.REFUNDED).aggregate(
            total=Sum("paid_amount_toman"),
        )["total"] or 0)
        months.append({
            "label": f"{y}/{m:02d}",
            "salons": Salon.objects.filter(created_at__gte=aware_start, created_at__lt=aware_end).count(),
            "bookings": Appointment.objects.filter(created_at__gte=aware_start, created_at__lt=aware_end).count(),
            "received": int(received),
        })
    max_bookings = max([p["bookings"] for p in months] or [1]) or 1
    for record in months:
        record["bar_width"] = round(record["bookings"] * 100 / max_bookings) if record["bookings"] else 0
    return render(request, "platform_admin/reports.html", {
        "days": days, "kpis": base, "months": months,
    })


@platform_required
def support_tickets(request):
    q = (request.GET.get("q") or "").strip()[:80]
    status = (request.GET.get("status") or "").strip()
    qs = SupportTicket.objects.select_related("salon", "opened_by")
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(salon__name__icontains=q))
    if status in SupportTicket.Status.values:
        qs = qs.filter(status=status)
    else:
        status = ""
    return render(request, "platform_admin/support.html", {
        "page": _page(request, qs.order_by("-last_activity_at")),
        "q": q, "status": status, "statuses": SupportTicket.Status.choices,
    })


@platform_required
def ticket_detail(request, ticket_id):
    ticket = get_object_or_404(SupportTicket.objects.select_related("salon", "opened_by"), pk=ticket_id)
    return render(request, "platform_admin/ticket_detail.html", {
        "ticket": ticket,
        "thread": ticket.messages.select_related("author").all(),
        "reply_form": MessageForm(),
        "statuses": SupportTicket.Status.choices,
        "priorities": SupportTicket.Priority.choices,
    })


@platform_required
@require_POST
def ticket_reply(request, ticket_id):
    action = request.POST.get("action", "reply")
    with transaction.atomic():
        ticket = get_object_or_404(SupportTicket.objects.select_for_update(), pk=ticket_id)
        if action == "reply":
            form = MessageForm(request.POST)
            if not form.is_valid():
                messages.error(request, "پاسخ خالی یا نامعتبر است؛ متن را بررسی کنید.")
                return redirect("platform_admin:ticket_detail", ticket_id=ticket_id)
            SupportMessage.objects.create(
                ticket=ticket, author=request.user, body=form.cleaned_data["body"],
                is_internal=request.POST.get("is_internal") == "on",
            )
            if ticket.status in (SupportTicket.Status.OPEN, SupportTicket.Status.RESOLVED):
                ticket.status = SupportTicket.Status.IN_PROGRESS
        elif action == "status":
            status = request.POST.get("status")
            priority = request.POST.get("priority")
            if status not in SupportTicket.Status.values or priority not in SupportTicket.Priority.values:
                messages.error(request, "وضعیت یا اولویت معتبر نیست.")
                return redirect("platform_admin:ticket_detail", ticket_id=ticket_id)
            ticket.status, ticket.priority = status, priority
        else:
            raise PermissionDenied
        ticket.last_activity_at = timezone.now()
        ticket.save(update_fields=["status", "priority", "last_activity_at", "updated_at"])
        _audit(request, AuditLog.Action.UPDATE, "platform_support", ticket.pk,
               "پاسخ یا وضعیت پشتیبانی به‌روز شد", ticket.salon)
    messages.success(request, "تغییرات درخواست پشتیبانی ثبت شد.")
    return redirect("platform_admin:ticket_detail", ticket_id=ticket_id)


@platform_required
def articles(request):
    q = (request.GET.get("q") or "").strip()[:80]
    status = request.GET.get("status", "")
    qs = BlogPost.objects.all()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(category__icontains=q))
    if status in BlogPost.Status.values:
        qs = qs.filter(status=status)
    else:
        status = ""
    return render(request, "platform_admin/articles.html", {
        "page": _page(request, qs.order_by("-created_at")),
        "q": q, "status": status,
    })


@platform_required
@require_http_methods(["GET", "POST"])
def article_edit(request, article_id=None):
    article = get_object_or_404(BlogPost, pk=article_id) if article_id is not None else None
    if request.method == "POST":
        form = ArticleForm(request.POST, request.FILES, instance=article)
        if form.is_valid():
            with transaction.atomic():
                saved = form.save(commit=False)
                if saved.status == BlogPost.Status.DRAFT:
                    saved.published_at = None
                saved.save()
                _audit(request, AuditLog.Action.UPDATE if article else AuditLog.Action.CREATE,
                       "platform_article", saved.pk, f"مقاله «{saved.title[:80]}» ذخیره شد")
            messages.success(request, "مقاله ذخیره شد.")
            return redirect("platform_admin:article_edit", article_id=saved.pk)
    else:
        form = ArticleForm(instance=article)
    return render(request, "platform_admin/article_edit.html", {"article": article, "form": form})


@platform_required
def audit(request):
    action = request.GET.get("action", "")
    q = (request.GET.get("q") or "").strip()[:80]
    logs = AuditLog.objects.select_related("actor", "salon")
    if action in AuditLog.Action.values:
        logs = logs.filter(action=action)
    else:
        action = ""
    if q:
        logs = logs.filter(
            Q(message__icontains=q) | Q(entity_type__icontains=q) | Q(salon__name__icontains=q)
        )
    return render(request, "platform_admin/audit.html", {
        "page": _page(request, logs.order_by("-created_at")),
        "action": action, "q": q, "actions": AuditLog.Action.choices,
    })


@platform_required
def system(request):
    return render(request, "platform_admin/system.html", {
        "diagnostics": {
            "debug_disabled": not settings.DEBUG,
            "sms_provider_configured": bool(getattr(settings, "BEAUTYOS_KAVENEGAR_API_KEY", "")),
            "automation_enabled": bool(getattr(settings, "BEAUTYOS_AUTOMATION_SEND_ENABLED", False)),
        },
        "tickets_open": SupportTicket.objects.filter(
            status__in=[SupportTicket.Status.OPEN, SupportTicket.Status.IN_PROGRESS]
        ).count(),
    })


# The salon support portal deliberately uses the existing tenant resolver and permissions.
@salon_required
@require_permission(P_SALON_SETTINGS)
def salon_support(request):
    return render(request, "platform_admin/salon_support.html", {
        "page": _page(request, SupportTicket.objects.filter(
            salon=request.salon
        ).order_by("-last_activity_at")),
    })


@salon_required
@require_permission(P_SALON_SETTINGS)
@require_http_methods(["GET", "POST"])
def salon_ticket_new(request):
    if request.method == "POST":
        form = TicketForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                ticket = form.save(commit=False)
                ticket.salon = request.salon
                ticket.opened_by = request.user
                ticket.save()
                SupportMessage.objects.create(
                    ticket=ticket, author=request.user,
                    body=form.cleaned_data["body"], is_internal=False,
                )
                _audit(request, AuditLog.Action.CREATE, "support_ticket", ticket.pk,
                       "درخواست پشتیبانی ایجاد شد", request.salon)
            messages.success(request, "درخواست شما ثبت شد.")
            return redirect("salon_support:detail", ticket_id=ticket.pk)
    else:
        form = TicketForm()
    return render(request, "platform_admin/salon_ticket_new.html", {"form": form})


@salon_required
@require_permission(P_SALON_SETTINGS)
@require_http_methods(["GET", "POST"])
def salon_ticket_detail(request, ticket_id):
    ticket = get_object_or_404(SupportTicket, pk=ticket_id, salon=request.salon)
    if request.method == "POST":
        if ticket.status == SupportTicket.Status.CLOSED:
            messages.error(request, "این درخواست بسته شده است؛ لطفاً درخواست تازه ثبت کنید.")
            return redirect("salon_support:detail", ticket_id=ticket.pk)
        form = MessageForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                ticket = SupportTicket.objects.select_for_update().get(pk=ticket.pk, salon=request.salon)
                SupportMessage.objects.create(
                    ticket=ticket, author=request.user,
                    body=form.cleaned_data["body"], is_internal=False,
                )
                if ticket.status == SupportTicket.Status.RESOLVED:
                    ticket.status = SupportTicket.Status.OPEN
                ticket.last_activity_at = timezone.now()
                ticket.save(update_fields=["last_activity_at", "status", "updated_at"])
            messages.success(request, "پیام شما ارسال شد.")
            return redirect("salon_support:detail", ticket_id=ticket.pk)
    else:
        form = MessageForm()
    return render(request, "platform_admin/salon_ticket_detail.html", {
        "ticket": ticket,
        "thread": ticket.messages.filter(is_internal=False).select_related("author"),
        "form": form,
    })


@platform_required
def public_inquiries(request):
    query = (request.GET.get("q") or "").strip()[:80]
    status = (request.GET.get("status") or "").strip()
    qs = ContactInquiry.objects.all()
    if query:
        qs = qs.filter(
            Q(name__icontains=query) | Q(phone__icontains=query)
            | Q(email__icontains=query) | Q(message__icontains=query)
        )
    if status in ContactInquiry.Status.values:
        qs = qs.filter(status=status)
    else:
        status = ""
    return render(request, "platform_admin/inquiries.html", {
        "page": _page(request, qs.order_by("-created_at")),
        "q": query, "status": status, "statuses": ContactInquiry.Status.choices,
    })


@platform_required
@require_http_methods(["GET", "POST"])
def public_inquiry_detail(request, inquiry_id):
    if request.method == "POST":
        status = (request.POST.get("status") or "").strip()
        note = (request.POST.get("internal_note") or "").strip()
        if status not in ContactInquiry.Status.values or len(note) > 3000:
            messages.error(request, "وضعیت یا یادداشت معتبر نیست.")
            return redirect("platform_admin:inquiry_detail", inquiry_id=inquiry_id)
        if status == ContactInquiry.Status.CLOSED and not note:
            messages.error(request, "برای بستن پیام، نتیجه پیگیری را در یادداشت داخلی ثبت کنید.")
            return redirect("platform_admin:inquiry_detail", inquiry_id=inquiry_id)
        with transaction.atomic():
            inquiry = get_object_or_404(ContactInquiry.objects.select_for_update(), pk=inquiry_id)
            inquiry.status = status
            inquiry.internal_note = note
            inquiry.handled_by = request.user
            inquiry.save(update_fields=["status", "internal_note", "handled_by", "updated_at"])
            _audit(
                request, AuditLog.Action.UPDATE, "public_inquiry", inquiry.pk,
                "وضعیت پیگیری پیام عمومی به‌روزرسانی شد",
            )
        messages.success(request, "وضعیت پیام ثبت شد.")
        return redirect("platform_admin:inquiry_detail", inquiry_id=inquiry_id)
    inquiry = get_object_or_404(ContactInquiry.objects.select_related("handled_by"), pk=inquiry_id)
    return render(request, "platform_admin/inquiry_detail.html", {
        "inquiry": inquiry, "statuses": ContactInquiry.Status.choices,
    })
