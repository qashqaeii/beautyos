import pytest

from apps.accounts.models import User
from apps.dashboard.role_services import appointment_payment_summary, get_manager_financial_summary, day_bounds
from apps.salons.models import SalonMembership
from django.utils import timezone


@pytest.mark.django_db
def test_dashboard_home_by_role(client, salon, owner_membership):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    assert client.get("/app/").status_code == 200


@pytest.mark.django_db
def test_receptionist_dashboard_not_old_desk_template(client, salon, owner_membership):
    receptionist = User.objects.create_user(phone="+989121234599", full_name="منشی")
    SalonMembership.objects.create(
        user=receptionist, salon=salon, role=SalonMembership.Role.RECEPTIONIST, is_active=True
    )
    client.force_login(receptionist)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    response = client.get("/app/")
    assert response.status_code == 200
    assert client.get("/reception/").status_code == 200
    assert "dashboard/reception_desk.html" in [t.name for t in client.get("/reception/").templates]


@pytest.mark.django_db
def test_manager_sees_management_and_specialists(client, salon, owner_membership):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    assert client.get("/app/management/").status_code == 200
    assert client.get("/app/specialists/").status_code == 200


@pytest.mark.django_db
def test_management_no_waitlist_packages_retention_cards(client, salon, owner_membership):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    html = client.get("/app/management/").content.decode()
    assert 'font-medium text-ink">لیست انتظار</span>' not in html
    assert 'font-medium text-ink">پکیج‌ها</span>' not in html
    assert 'font-medium text-ink">پیگیری مشتری</span>' not in html


@pytest.mark.django_db
def test_reception_quick_access_for_owner_and_receptionist(client, salon, owner_membership):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    owner_html = client.get("/reception/").content.decode()
    assert "دسترسی سریع" in owner_html
    assert "/waitlist/" in owner_html
    assert 'reception-desk-quick__label">پکیج‌ها</span>' in owner_html
    assert "/retention/" in owner_html

    receptionist = User.objects.create_user(phone="+989121234596", full_name="منشی۴")
    SalonMembership.objects.create(
        user=receptionist, salon=salon, role=SalonMembership.Role.RECEPTIONIST, is_active=True
    )
    client.force_login(receptionist)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    reception_html = client.get("/reception/").content.decode()
    assert "دسترسی سریع" in reception_html
    assert reception_html.count("reception-desk-quick__link") == 3
    assert 'reception-desk-quick__label">فروش پکیج</span>' in reception_html
    assert 'reception-desk-header__title' in reception_html


@pytest.mark.django_db
def test_reception_quick_link_destinations(client, salon, owner_membership):
    receptionist = User.objects.create_user(phone="+989121234595", full_name="منشی۵")
    SalonMembership.objects.create(
        user=receptionist, salon=salon, role=SalonMembership.Role.RECEPTIONIST, is_active=True
    )

    for user in (owner_membership.user, receptionist):
        client.force_login(user)
        session = client.session
        session["active_salon_id"] = str(salon.id)
        session.save()
        assert client.get("/waitlist/").status_code == 200
        assert client.get("/retention/").status_code == 200
        if user == owner_membership.user:
            assert client.get("/packages/").status_code == 200
        else:
            assert client.get("/packages/sell/").status_code == 200


@pytest.mark.django_db
def test_receptionist_no_management(client, salon, owner_membership):
    receptionist = User.objects.create_user(phone="+989121234597", full_name="منشی۳")
    SalonMembership.objects.create(
        user=receptionist, salon=salon, role=SalonMembership.Role.RECEPTIONIST, is_active=True
    )
    client.force_login(receptionist)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    assert client.get("/app/management/").status_code == 403


@pytest.mark.django_db
def test_receptionist_staff_manage_grant(client, salon, owner_membership):
    receptionist = User.objects.create_user(phone="+989121234598", full_name="منشی۲")
    m = SalonMembership.objects.create(
        user=receptionist,
        salon=salon,
        role=SalonMembership.Role.RECEPTIONIST,
        is_active=True,
        can_manage_staff=True,
    )
    client.force_login(receptionist)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    assert client.get("/staff/").status_code == 200
    m.can_manage_staff = False
    m.save()
    assert client.get("/staff/").status_code == 403


@pytest.mark.django_db
def test_appointment_payment_summary_no_payment(salon):
    from apps.appointments.models import Appointment
    from apps.customers.models import Customer
    from apps.services.models import Service
    from apps.staff.models import StaffProfile
    from datetime import timedelta

    customer = Customer.objects.create(salon=salon, full_name="تست", phone="09120000001")
    service = Service.objects.create(salon=salon, name="اصلاح", duration_minutes=30, price_toman=500_000)
    membership = SalonMembership.objects.create(
        user=User.objects.create_user(phone="+989121200001", full_name="متخصص"),
        salon=salon,
        role=SalonMembership.Role.SPECIALIST,
    )
    staff = StaffProfile.objects.create(salon=salon, membership=membership, display_name="متخصص")
    appt = Appointment.objects.create(
        salon=salon,
        customer=customer,
        staff=staff,
        service=service,
        start_at=timezone.now() + timedelta(hours=2),
        end_at=timezone.now() + timedelta(hours=2, minutes=30),
        price_toman=500_000,
        status=Appointment.Status.CONFIRMED,
    )
    summary = appointment_payment_summary(appt)
    assert summary["owed_toman"] == 500_000

    today_start, today_end = day_bounds(timezone.localdate())
    summary_mgr = get_manager_financial_summary(salon, today_start, today_end, today_start, today_end)
    assert "total_received" in summary_mgr


@pytest.mark.django_db
def test_management_editorial_design_preserves_links(client, salon, owner_membership):
    from django.contrib.staticfiles import finders
    from django.urls import reverse

    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    response = client.get(reverse("dashboard:management"))
    assert response.status_code == 200
    html = response.content.decode()
    assert "luna-management-shell" in html
    assert "luna-management.css" in html
    assert "beautyos-management-floral.webp" in html
    assert html.count('class="dashboard-mgmt-card"') == len(response.context["links"]) == 11
    for link in response.context["links"]:
        assert f'href="{link["url"]}"' in html
    assert finders.find("css/luna-management.css")
    assert finders.find("images/photos/beautyos-management-floral.webp")


@pytest.mark.django_db
def test_management_receptionist_cards_match_destination_permissions(client, salon):
    from django.urls import reverse

    receptionist = User.objects.create_user(phone="+989121234591", full_name="منشی")
    membership = SalonMembership.objects.create(
        user=receptionist, salon=salon, role=SalonMembership.Role.RECEPTIONIST,
        is_active=True, can_manage_staff=True,
    )
    client.force_login(receptionist)
    response = client.get(reverse("dashboard:management"))
    assert response.status_code == 200
    urls = {link["url"] for link in response.context["links"]}
    assert urls == {reverse("staff:list"), reverse("customers:list")}
    for url in urls:
        assert client.get(url).status_code == 200
    for name in ("services:list", "portfolio:list", "finance:overview"):
        assert reverse(name) not in urls
        assert client.get(reverse(name)).status_code == 403
    membership.can_manage_staff = False
    membership.save(update_fields=["can_manage_staff"])
    assert client.get(reverse("dashboard:management")).status_code == 403


@pytest.mark.django_db
def test_management_inactive_membership_cannot_see_navigation(owner_membership):
    from apps.dashboard.nav import can_see_management

    owner_membership.is_active = False
    assert not can_see_management(owner_membership)
