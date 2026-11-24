"""Phase 5: prepaid session, cancellation reversal, material cost and tenant safety."""
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.appointments.models import Appointment
from apps.appointments.services.lifecycle import cancel_appointment, complete_appointment
from apps.audit.models import AuditLog
from apps.customers.models import Customer
from apps.dashboard.role_services import appointment_payment_summary
from apps.finance.checkout import issue_invoice
from apps.finance.models import MaterialCost, Payment
from apps.inventory.models import InventoryItem
from apps.packages.models import CustomerPackage, PackageSessionUse, ServicePackage
from apps.packages.services import consume_package_session
from apps.salons.models import SalonMembership
from apps.services.models import Service
from apps.staff.models import StaffProfile


@pytest.fixture
def package_visit(salon, owner_membership):
    customer = Customer.objects.create(
        salon=salon, full_name="سحر مهربان", phone="+989121177451",
    )
    staff, _ = StaffProfile.objects.get_or_create(
        salon=salon, membership=owner_membership,
        defaults={"display_name": "متخصص پوست"},
    )
    service = Service.objects.create(
        salon=salon, name="مراقبت و پاکسازی پوست", duration_minutes=45,
        price_toman=850_000,
    )
    start = timezone.now() - timedelta(hours=3)
    visit = Appointment.objects.create(
        salon=salon, customer=customer, staff=staff, service=service,
        start_at=start, end_at=start + timedelta(minutes=45),
        status=Appointment.Status.CONFIRMED, price_toman=850_000,
    )
    complete_appointment(salon=salon, appointment_id=visit.pk)
    package = ServicePackage.objects.create(
        salon=salon, name="پکیج مراقبت پوست", price_toman=2_100_000,
        session_count=3, validity_days=90,
    )
    purchase = CustomerPackage.objects.create(
        salon=salon, customer=customer, package=package,
        sessions_total=3, sessions_used=0,
        expires_at=timezone.now() + timedelta(days=90),
        price_paid_toman=2_100_000,
    )
    return visit, purchase


def login(client, membership):
    client.force_login(membership.user)
    session = client.session
    session["active_salon_id"] = str(membership.salon_id)
    session.save()


@pytest.mark.django_db
def test_redeem_completed_visit_from_detail_without_double_collection(
    client, salon, owner_membership, package_visit,
):
    visit, purchase = package_visit
    login(client, owner_membership)
    detail_url = reverse("appointments:detail", args=[visit.pk])
    redeem_url = reverse("packages:use_session", args=[visit.pk])
    page = client.get(detail_url)
    assert page.status_code == 200
    assert "استفاده از پکیج مشتری" in page.content.decode()
    assert str(purchase.pk) in page.content.decode()
    assert page.context["available_packages"][0].pk == purchase.pk
    assert client.get(redeem_url).status_code == 405

    result = client.post(redeem_url, {"customer_package": purchase.pk})
    assert result.status_code == 302
    purchase.refresh_from_db()
    assert purchase.sessions_used == 1
    use = PackageSessionUse.scoped(salon).get(appointment=visit)
    assert use.reversed_at is None
    assert AuditLog.objects.filter(
        salon=salon, entity_type="package_session_use", entity_id=str(use.pk),
    ).count() == 1

    payment = appointment_payment_summary(Appointment.scoped(salon).get(pk=visit.pk))
    assert payment["owed_toman"] == 0
    assert payment["covered_by_package"] is True
    detail = client.get(detail_url)
    assert "پوشش با پکیج" in detail.content.decode()
    assert "دریافت مجدد لازم نیست" in detail.content.decode()
    assert "صدور فاکتور و تسویه" not in detail.content.decode()
    assert detail.context["available_packages"] == []

    desk = client.get(reverse("reception:desk"), {
        "day": timezone.localdate(visit.start_at).isoformat(),
    })
    assert desk.status_code == 200
    assert desk.context["day_operations_summary"]["outstanding_toman"] == 0
    assert desk.context["day_operations"][0]["can_checkout"] is False

    # A prepaid session must not be charged again via the invoice service.
    with pytest.raises(ValidationError):
        issue_invoice(
            salon=salon, customer_id=visit.customer_id,
            appointment_ids=[visit.pk], request_key=uuid4(), discount=0,
            amounts={"cash": 0, "card": 850_000, "transfer": 0},
            actor=owner_membership.user,
        )
    client.post(redeem_url, {"customer_package": purchase.pk})
    purchase.refresh_from_db()
    assert purchase.sessions_used == 1
    assert PackageSessionUse.scoped(salon).filter(appointment=visit).count() == 1


@pytest.mark.django_db
def test_cancel_completed_package_visit_restores_session_and_audits(
    salon, owner_membership, package_visit,
):
    visit, purchase = package_visit
    use = consume_package_session(purchase, visit, actor=owner_membership.user)
    purchase.refresh_from_db()
    assert purchase.sessions_remaining == 2
    canceled = cancel_appointment(salon=salon, appointment_id=visit.pk)
    assert canceled.status == Appointment.Status.CANCELLED
    purchase.refresh_from_db()
    use.refresh_from_db()
    assert purchase.sessions_used == 0
    assert purchase.sessions_remaining == 3
    assert use.reversed_at is not None
    assert AuditLog.objects.filter(
        salon=salon, entity_type="package_session_reversal", entity_id=str(use.pk),
    ).count() == 1
    assert cancel_appointment(salon=salon, appointment_id=visit.pk).pk == visit.pk
    assert AuditLog.objects.filter(
        salon=salon, entity_type="package_session_reversal",
    ).count() == 1


@pytest.mark.django_db
def test_package_requires_completed_unpaid_non_invoiced_and_same_tenant(
    client, salon, salon_b, owner_membership, package_visit,
):
    visit, purchase = package_visit
    foreign_customer = Customer.objects.create(
        salon=salon_b, full_name="مشتری سالن دیگر", phone="+989121177453",
    )
    foreign_package = ServicePackage.objects.create(
        salon=salon_b, name="پکیج دیگر", price_toman=900_000, session_count=2,
    )
    foreign_purchase = CustomerPackage.objects.create(
        salon=salon_b, customer=foreign_customer, package=foreign_package,
        sessions_total=2, price_paid_toman=900_000,
        expires_at=timezone.now() + timedelta(days=30),
    )
    with pytest.raises(ValidationError):
        consume_package_session(foreign_purchase, visit)
    visit.status = Appointment.Status.CONFIRMED
    visit.save(update_fields=["status", "updated_at"])
    with pytest.raises(ValidationError, match="تکمیل"):
        consume_package_session(purchase, visit)
    visit.status = Appointment.Status.COMPLETED
    visit.save(update_fields=["status", "updated_at"])
    payment = Payment.objects.create(
        salon=salon, customer=visit.customer, appointment=visit,
        total_amount_toman=850_000, paid_amount_toman=100_000,
        status=Payment.Status.PARTIAL,
    )
    with pytest.raises(ValidationError, match="دریافت"):
        consume_package_session(purchase, visit)
    assert purchase.sessions_used == 0
    payment.delete()
    login(client, owner_membership)
    url = reverse("packages:use_session", args=[visit.pk])
    assert client.post(url, {"customer_package": foreign_purchase.pk}).status_code == 404
    assert purchase.sessions_used == 0


@pytest.mark.django_db
def test_package_redeem_requires_permission_and_csrf(
    salon, owner_membership, package_visit,
):
    visit, purchase = package_visit
    url = reverse("packages:use_session", args=[visit.pk])
    strict = Client(enforce_csrf_checks=True)
    login(strict, owner_membership)
    assert strict.post(url, {"customer_package": purchase.pk}).status_code == 403

    other = User.objects.create_user(phone="+989121177459", full_name="متخصص فاقد دسترسی")
    membership = SalonMembership.objects.create(
        salon=salon, user=other, role=SalonMembership.Role.SPECIALIST,
    )
    client = Client()
    login(client, membership)
    assert client.post(url, {"customer_package": purchase.pk}).status_code == 403
    purchase.refresh_from_db()
    assert purchase.sessions_used == 0


@pytest.mark.django_db
def test_material_deep_link_prefills_visit_and_records_real_stock_cost(
    client, salon, owner_membership, package_visit,
):
    visit, purchase = package_visit
    item = InventoryItem.objects.create(
        salon=salon, name="ماسک مراقبت", unit=InventoryItem.Unit.GRAM,
        quantity=Decimal("25.00"), purchase_price_toman=12_000,
    )
    login(client, owner_membership)
    link = reverse("finance:materials") + f"?appointment={visit.pk}"
    response = client.get(link)
    assert response.status_code == 200
    assert response.context["selected_appointment"].pk == visit.pk
    assert response.context["consume_form"]["appointment"].value() == visit.pk
    assert "نوبت انتخاب‌شده" in response.content.decode()

    result = client.post(link, {
        "action": "consume", "appointment": visit.pk, "item": item.pk,
        "quantity": "2.50", "request_key": str(uuid4()),
    })
    assert result.status_code == 302
    assert result.url == reverse("appointments:detail", args=[visit.pk])
    item.refresh_from_db()
    assert item.quantity == Decimal("22.50")
    cost = MaterialCost.scoped(salon).get(appointment=visit)
    assert cost.cost_toman == 30_000
    assert client.get(result.url).context["material_cost_total"] == 30_000

    # Materials are a separate cost ledger; they must not create payment rows.
    assert Payment.scoped(salon).filter(appointment=visit).count() == 0


@pytest.mark.django_db
def test_expired_package_or_already_invoiced_visit_cannot_consume(
    salon, owner_membership, package_visit,
):
    visit, purchase = package_visit
    purchase.expires_at = timezone.now() - timedelta(days=1)
    purchase.save(update_fields=["expires_at"])
    with pytest.raises(ValidationError, match="منقضی"):
        consume_package_session(purchase, visit)
    purchase.expires_at = timezone.now() + timedelta(days=10)
    purchase.save(update_fields=["expires_at"])

    issue_invoice(
        salon=salon, customer_id=visit.customer_id,
        appointment_ids=[visit.pk], request_key=uuid4(), discount=0,
        amounts={"cash": 0, "card": 0, "transfer": 0},
        actor=owner_membership.user,
    )
    with pytest.raises(ValidationError, match="فاکتور"):
        consume_package_session(purchase, visit)
    purchase.refresh_from_db()
    assert purchase.sessions_used == 0
    assert PackageSessionUse.scoped(salon).filter(appointment=visit).count() == 0
