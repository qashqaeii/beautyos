import pytest
from django.urls import reverse

from apps.commissions.forms import SettlementForm
from apps.commissions.models import CommissionEntry
from apps.core.utils.money import format_toman_fa, parse_toman_input
from apps.staff.models import StaffProfile


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1320024", 1320024),
        ("۱.۳۲۰.۰۲۴", 1320024),
        ("1.320.024", 1320024),
        ("۱٬۳۲۰٬۰۲۴", 1320024),
        ("900", 900),
    ],
)
def test_parse_toman_input(raw, expected):
    assert parse_toman_input(raw) == expected


def test_format_toman_fa():
    assert format_toman_fa(1320024) == "۱.۳۲۰.۰۲۴"
    assert format_toman_fa(1000) == "۱.۰۰۰"
    assert format_toman_fa(900) == "۹۰۰"


def test_settlement_form_accepts_formatted_amount():
    form = SettlementForm({"amount_toman": "۱.۳۲۰.۰۲۴", "note": ""})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["amount_toman"] == 1320024


def test_settlement_form_requires_amount():
    form = SettlementForm({"amount_toman": "", "note": ""})
    assert not form.is_valid()
    assert "amount_toman" in form.errors


@pytest.mark.django_db
def test_settle_staff_page_posts_exact_toman(client, owner_membership, salon):
    from datetime import timedelta

    from django.utils import timezone

    from apps.appointments.models import Appointment
    from apps.commissions.models import CommissionSettlement
    from apps.customers.models import Customer
    from apps.services.models import Service

    customer = Customer.objects.create(salon=salon, full_name="مشتری", phone="+989129999999")
    service = Service.objects.create(
        salon=salon, name="خدمت", duration_minutes=30, price_toman=1320024
    )
    staff = StaffProfile.objects.create(
        salon=salon,
        membership=owner_membership,
        display_name="متخصص تسویه",
        is_bookable=True,
    )
    start = timezone.now() - timedelta(hours=2)
    appt = Appointment.objects.create(
        salon=salon,
        customer=customer,
        staff=staff,
        service=service,
        start_at=start,
        end_at=start + timedelta(minutes=30),
        status=Appointment.Status.COMPLETED,
        price_toman=1320024,
    )
    entry = CommissionEntry.objects.get(appointment=appt)
    entry.commission_amount_toman = 1320024
    entry.base_amount_toman = 1320024
    entry.status = CommissionEntry.Status.RECOGNIZED
    entry.save(update_fields=["commission_amount_toman", "base_amount_toman", "status"])
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    url = reverse("commissions:settle", kwargs={"staff_id": staff.pk})
    response = client.get(url)
    assert response.status_code == 200
    html = response.content.decode()
    assert "۱.۳۲۰.۰۲۴" in html
    assert 'amount: 1320024' in html
    before = CommissionSettlement.objects.count()
    post = client.post(url, {"amount_toman": "1320024", "note": "تست"})
    assert post.status_code == 302
    assert CommissionSettlement.objects.count() == before + 1
    assert CommissionSettlement.objects.latest("pk").amount_toman == 1320024
