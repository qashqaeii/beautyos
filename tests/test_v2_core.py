import pytest
from django.utils import timezone

from apps.commissions.services import recognize_commission_for_appointment
from apps.salons.models import SalonMembership, SalonSettings
from apps.salons.themes import GLOBAL_DASHBOARD_THEME, css_variables_for_dashboard, resolve_salon_dashboard_theme


@pytest.mark.django_db
def test_existing_salon_backfilled_onboarding(owner_membership):
    assert owner_membership.salon.settings.onboarding_completed_at is not None


@pytest.mark.django_db
def test_dashboard_theme_global_despite_stored_per_salon(owner_membership, salon_b, user):
    owner_membership.salon.settings.dashboard_theme = SalonSettings.DashboardTheme.ROSE_ATELIER
    owner_membership.salon.settings.save()
    salon_b.settings.dashboard_theme = SalonSettings.DashboardTheme.MODERN_GENTLEMAN
    salon_b.settings.save()
    assert resolve_salon_dashboard_theme(owner_membership.salon) == GLOBAL_DASHBOARD_THEME
    assert resolve_salon_dashboard_theme(salon_b) == GLOBAL_DASHBOARD_THEME
    a = css_variables_for_dashboard(owner_membership.salon.settings.dashboard_theme)
    b = css_variables_for_dashboard(salon_b.settings.dashboard_theme)
    assert a["--color-accent"] == b["--color-accent"] == "#B58D89"


@pytest.mark.django_db
def test_commission_not_duplicated(salon, owner_membership):
    from apps.appointments.models import Appointment
    from apps.customers.models import Customer
    from apps.services.models import Service
    from apps.staff.models import StaffProfile
    from django.utils import timezone
    from datetime import timedelta

    customer = Customer.objects.create(salon=salon, full_name="مشتری", phone="+989121111111")
    service = Service.objects.create(salon=salon, name="تست", duration_minutes=30, price_toman=100000)
    staff = StaffProfile.objects.create(
        salon=salon,
        membership=owner_membership,
        display_name="متخصص",
        is_bookable=True,
    )
    start = timezone.now() - timedelta(hours=1)
    appt = Appointment.objects.create(
        salon=salon,
        customer=customer,
        staff=staff,
        service=service,
        start_at=start,
        end_at=start + timedelta(minutes=30),
        status=Appointment.Status.COMPLETED,
        price_toman=100000,
    )
    from apps.commissions.models import CommissionEntry

    assert CommissionEntry.objects.filter(appointment=appt).count() == 1
    entry = CommissionEntry.objects.get(appointment=appt)
    assert recognize_commission_for_appointment(appt) == entry
