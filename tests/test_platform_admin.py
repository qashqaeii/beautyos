"""Central platform management: access control, tenant isolation and audit regression."""
from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.appointments.models import Appointment
from apps.audit.models import AuditLog
from apps.finance.models import Payment
from apps.platform_admin.models import SupportMessage, SupportTicket
from apps.salons.models import Salon, SalonMembership
from apps.website.models import BlogPost


@pytest.fixture
def platform_operator(db):
    return User.objects.create_superuser(
        phone="+989101010001", full_name="مدیر مرکزی", password="strong-test-only-password"
    )


@pytest.fixture
def platform_client(client, platform_operator):
    client.force_login(platform_operator)
    return client


@pytest.mark.django_db
@pytest.mark.parametrize("url_name", [
    "overview", "salons", "users", "reports", "support", "articles", "audit", "system",
])
def test_central_pages_are_private_and_superuser_only(client, owner_membership, url_name, platform_operator):
    url = reverse(f"platform_admin:{url_name}")
    assert client.get(url).status_code == 302
    client.force_login(owner_membership.user)
    assert client.get(url).status_code == 403
    staff_user = User.objects.create_user(phone="+989101010002", full_name="اپراتور")
    staff_user.is_staff = True
    staff_user.save(update_fields=["is_staff"])
    client.force_login(staff_user)
    assert client.get(url).status_code == 403
    client.force_login(platform_operator)
    assert client.get(url).status_code == 200


@pytest.mark.django_db
def test_superuser_without_salon_can_access_control_center_and_login_redirect(client, platform_operator):
    assert not SalonMembership.objects.filter(user=platform_operator).exists()
    client.force_login(platform_operator)
    assert client.get(reverse("platform_admin:overview")).status_code == 200
    response = client.get(reverse("accounts:login"))
    assert response.status_code == 302
    assert response.url == reverse("platform_admin:overview")
    assert "/control/" == reverse("platform_admin:overview")


@pytest.mark.django_db
def test_dashboard_numbers_are_real_and_salon_turnover_is_not_platform_revenue(
    platform_client, salon, owner_membership
):
    from apps.customers.models import Customer
    customer = Customer.objects.create(salon=salon, full_name="کاربر", phone="+989121246810")
    Payment.objects.create(salon=salon, customer=customer, total_amount_toman=600000,
                           paid_amount_toman=500000, status=Payment.Status.PAID)
    Payment.objects.create(salon=salon, customer=customer, total_amount_toman=300000,
                           paid_amount_toman=300000, status=Payment.Status.REFUNDED)
    response = platform_client.get(reverse("platform_admin:overview"), {"days": "30"})
    assert response.status_code == 200
    assert response.context["kpis"]["salons_total"] >= 1
    assert response.context["kpis"]["salon_receipts_toman"] == 500000
    assert "نه درآمد BeautyOS" in response.content.decode()


@pytest.mark.django_db
def test_salon_status_is_post_only_requires_reason_and_logs(platform_client, salon):
    url = reverse("platform_admin:salon_status", kwargs={"salon_id": salon.pk})
    assert platform_client.get(url).status_code == 405
    assert platform_client.post(url, {"action": "deactivate", "reason": "کم"}).status_code == 302
    salon.refresh_from_db()
    assert salon.is_active
    response = platform_client.post(url, {
        "action": "deactivate", "reason": "درخواست مستند از مالک سالن",
    })
    assert response.status_code == 302
    salon.refresh_from_db()
    assert not salon.is_active
    assert AuditLog.objects.filter(
        entity_type="platform_salon_status", entity_id=str(salon.pk),
        action=AuditLog.Action.SECURITY,
    ).exists()
    # Re-activation does not silently switch public booking on.
    salon.is_accepting_bookings = False
    salon.save(update_fields=["is_accepting_bookings"])
    platform_client.post(url, {"action": "activate", "reason": "بررسی و رفع درخواست مالک"})
    salon.refresh_from_db()
    assert salon.is_active
    assert salon.is_accepting_bookings is False


@pytest.mark.django_db
def test_user_status_protects_platform_operator_and_self(platform_client, platform_operator, owner_membership):
    own = reverse("platform_admin:user_status", kwargs={"user_id": platform_operator.pk})
    with pytest.raises(PermissionDenied):
        # Direct view invocation here validates the explicit central-operator protection.
        from django.test import RequestFactory
        from apps.platform_admin.views import user_status
        req = RequestFactory().post(own, {
            "action": "deactivate", "reason": "درخواست تست بسیار مشخص",
        })
        req.user = platform_operator
        user_status(req, platform_operator.pk)
    another = reverse("platform_admin:user_status", kwargs={"user_id": owner_membership.user.pk})
    assert platform_client.get(another).status_code == 405
    assert platform_client.post(another, {
        "action": "deactivate", "reason": "حساب نیازمند بررسی امنیتی",
    }).status_code == 302
    owner_membership.user.refresh_from_db()
    assert owner_membership.user.is_active is False
    assert AuditLog.objects.filter(entity_type="platform_user_status").count() == 1


@pytest.mark.django_db
def test_tenant_support_create_reply_and_isolated_access(
    client, owner_membership, salon_b, platform_operator
):
    user = owner_membership.user
    client.force_login(user)
    session = client.session
    session["active_salon_id"] = str(owner_membership.salon_id)
    session.save()
    assert client.get(reverse("salon_support:home")).status_code == 200
    create = client.post(reverse("salon_support:new"), {
        "title": "مشکل در تقویم نوبت", "category": "technical",
        "body": "در انتخاب ساعت نیاز به راهنمایی داریم.",
    })
    ticket = SupportTicket.objects.get(salon=owner_membership.salon)
    assert create.status_code == 302
    assert create.url == reverse("salon_support:detail", kwargs={"ticket_id": ticket.pk})
    assert ticket.opened_by_id == user.pk
    assert ticket.messages.filter(is_internal=False).count() == 1

    # A support note marked internal must never appear for salon members.
    SupportMessage.objects.create(
        ticket=ticket, author=platform_operator,
        body="یادداشت محرمانه مدیریتی", is_internal=True,
    )
    response = client.get(reverse("salon_support:detail", kwargs={"ticket_id": ticket.pk}))
    assert response.status_code == 200
    assert "یادداشت محرمانه مدیریتی" not in response.content.decode()

    other_owner = User.objects.create_user(phone="+989101010003", full_name="مالک دیگر")
    SalonMembership.objects.create(user=other_owner, salon=salon_b,
                                   role=SalonMembership.Role.OWNER)
    client.force_login(other_owner)
    session = client.session
    session["active_salon_id"] = str(salon_b.pk)
    session.save()
    assert client.get(reverse("salon_support:detail", kwargs={"ticket_id": ticket.pk})).status_code == 404
    assert client.post(reverse("salon_support:detail", kwargs={"ticket_id": ticket.pk}),
                       {"body": "دسترسی غیرمجاز"}).status_code == 404


@pytest.mark.django_db
def test_central_support_status_reply_and_internal_note(
    platform_client, salon, owner_membership
):
    ticket = SupportTicket.objects.create(
        salon=salon, opened_by=owner_membership.user, title="درخواست راهنمایی",
    )
    page = platform_client.get(reverse("platform_admin:ticket_detail", kwargs={"ticket_id": ticket.pk}))
    assert page.status_code == 200
    url = reverse("platform_admin:ticket_reply", kwargs={"ticket_id": ticket.pk})
    sent = platform_client.post(url, {
        "action": "reply", "body": "بررسی شد؛ لطفاً دوباره تست کنید.",
        "is_internal": "on",
    })
    assert sent.status_code == 302
    ticket.refresh_from_db()
    assert ticket.status == SupportTicket.Status.IN_PROGRESS
    assert SupportMessage.objects.get(ticket=ticket).is_internal
    assert AuditLog.objects.filter(entity_type="platform_support", entity_id=str(ticket.pk)).exists()
    changed = platform_client.post(url, {
        "action": "status", "status": "resolved", "priority": "high",
    })
    assert changed.status_code == 302
    ticket.refresh_from_db()
    assert ticket.status == SupportTicket.Status.RESOLVED
    assert ticket.priority == SupportTicket.Priority.HIGH


@pytest.mark.django_db
def test_salon_employee_cannot_access_support_management(client, salon, owner_membership):
    employee = User.objects.create_user(phone="+989101010004", full_name="کارمند")
    SalonMembership.objects.create(
        user=employee, salon=salon, role=SalonMembership.Role.SPECIALIST
    )
    client.force_login(employee)
    session = client.session
    session["active_salon_id"] = str(salon.pk)
    session.save()
    assert client.get(reverse("salon_support:home")).status_code == 403
    assert client.post(reverse("salon_support:new"), {
        "title": "تلاش", "category": "general", "body": "پیام",
    }).status_code == 403
    assert SupportTicket.objects.count() == 0


@pytest.mark.django_db
def test_blog_editor_handles_draft_publish_and_public_visibility(platform_client):
    url = reverse("platform_admin:article_new")
    created = platform_client.post(url, {
        "title": "راهنمای مدیریت سالن", "slug": "",
        "summary": "نکات بهینه‌سازی مدیریت سالن",
        "body": "نکات روزمره سالن زیبایی",
        "category": "آموزش", "status": "draft",
    })
    assert created.status_code == 302
    article = BlogPost.objects.get(title="راهنمای مدیریت سالن")
    assert article.status == BlogPost.Status.DRAFT
    assert article.published_at is None
    assert platform_client.get(reverse("website:blog_post",
                                       kwargs={"slug": article.slug})).status_code == 404
    url = reverse("platform_admin:article_edit", kwargs={"article_id": article.pk})
    published = platform_client.post(url, {
        "title": article.title, "slug": article.slug,
        "summary": article.summary, "body": article.body,
        "category": article.category, "status": "published",
    })
    assert published.status_code == 302
    article.refresh_from_db()
    assert article.published_at is not None
    assert platform_client.get(reverse("website:blog_post",
                                       kwargs={"slug": article.slug})).status_code == 200
    assert AuditLog.objects.filter(entity_type="platform_article", entity_id=str(article.pk)).count() == 2


@pytest.mark.django_db
def test_article_publishing_requires_summary_and_content(platform_client):
    invalid = platform_client.post(reverse("platform_admin:article_new"), {
        "title": "مقاله ناقص", "slug": "missing-body",
        "summary": "", "body": "", "category": "",
        "status": "published",
    })
    assert invalid.status_code == 200
    assert "برای انتشار" in invalid.content.decode()
    assert BlogPost.objects.count() == 0


@pytest.mark.django_db
def test_operational_reports_queries_are_read_only(platform_client, owner_membership):
    before = (
        Salon.objects.count(),
        User.objects.count(),
        Appointment.objects.count(),
        SupportTicket.objects.count(),
    )
    for name in ("overview", "reports", "salons", "users", "articles", "support", "audit", "system"):
        assert platform_client.get(reverse("platform_admin:" + name)).status_code == 200
    after = (
        Salon.objects.count(),
        User.objects.count(),
        Appointment.objects.count(),
        SupportTicket.objects.count(),
    )
    assert before == after


@pytest.mark.django_db
def test_platform_post_actions_require_csrf(platform_operator, salon):
    secured = Client(enforce_csrf_checks=True)
    secured.force_login(platform_operator)
    action_url = reverse("platform_admin:salon_status", kwargs={"salon_id": salon.pk})
    assert secured.post(action_url, {
        "action": "deactivate", "reason": "دلیل آزمایشی و مشخص",
    }).status_code == 403
    salon.refresh_from_db()
    assert salon.is_active
