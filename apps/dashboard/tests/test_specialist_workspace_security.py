"""Regression checks for specialist-only workspace and appointment isolation."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase
from django.core.exceptions import ValidationError
from apps.appointments.forms import AppointmentForm

from apps.appointments.views import _appointment_qs
from apps.salons.models import SalonMembership


class SpecialistIsolationTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.salon = SimpleNamespace(pk="salon-a")
        self.profile = SimpleNamespace(pk=11, salon_id="salon-a", is_active=True, is_deleted=False)

    def request(self, role=SalonMembership.Role.SPECIALIST, profile=None):
        request = self.factory.get("/dashboard/my-workspace/?staff=999")
        request.salon = self.salon
        request.membership = SimpleNamespace(
            role=role, is_active=True,
            staff_profile=self.profile if profile is None else profile,
        )
        return request

    @patch("apps.appointments.views.StaffProfile.scoped")
    @patch("apps.appointments.views.Appointment.scoped")
    def test_appointment_query_always_filters_to_own_profile(self, scoped, staff_scoped):
        staff_scoped.return_value.filter.return_value.exists.return_value = True
        request = self.request()
        _appointment_qs(request)
        scoped.return_value.select_related.return_value.filter.assert_any_call(staff=self.profile)

    @patch("apps.appointments.views.StaffProfile.scoped")
    @patch("apps.appointments.views.Appointment.scoped")
    def test_missing_profile_returns_no_appointments(self, scoped, staff_scoped):
        staff_scoped.return_value.filter.return_value.exists.return_value = True
        request = self.request()
        request.membership.staff_profile = None
        _appointment_qs(request)
        scoped.return_value.select_related.return_value.none.assert_called_once()

    @patch("apps.appointments.views.StaffProfile.scoped")
    @patch("apps.appointments.views.Appointment.scoped")
    def test_foreign_salon_profile_returns_no_appointments(self, scoped, staff_scoped):
        staff_scoped.return_value.filter.return_value.exists.return_value = True
        request = self.request()
        request.membership.staff_profile = SimpleNamespace(
            pk=22, salon_id="salon-b", is_active=True, is_deleted=False
        )
        _appointment_qs(request)
        scoped.return_value.select_related.return_value.none.assert_called_once()


class SpecialistBookingGuardTests(SimpleTestCase):
    def test_forged_other_staff_rejected_at_form_validation(self):
        form = AppointmentForm.__new__(AppointmentForm)
        form.salon = SimpleNamespace(pk="salon-a")
        form.membership = SimpleNamespace(
            role=SalonMembership.Role.SPECIALIST,
            staff_profile=SimpleNamespace(pk=11, salon_id="salon-a"),
        )
        form.locked_staff = None
        form.cleaned_data = {
            "staff": SimpleNamespace(
                pk=22, salon_id="salon-a", is_deleted=False,
                is_active=True, is_bookable=True,
            )
        }
        with self.assertRaises(ValidationError) as caught:
            form.clean_staff()
        self.assertEqual(caught.exception.messages, ["فقط می‌توانید برای خودتان نوبت ثبت کنید."])

    def test_own_staff_accepted_at_form_validation(self):
        form = AppointmentForm.__new__(AppointmentForm)
        form.salon = SimpleNamespace(pk="salon-a")
        form.membership = SimpleNamespace(
            role=SalonMembership.Role.SPECIALIST,
            staff_profile=SimpleNamespace(pk=11, salon_id="salon-a"),
        )
        form.locked_staff = None
        own_staff = SimpleNamespace(
            pk=11, salon_id="salon-a", is_deleted=False,
            is_active=True, is_bookable=True,
        )
        form.cleaned_data = {"staff": own_staff}
        self.assertIs(form.clean_staff(), own_staff)
