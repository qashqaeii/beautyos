"""Regression checks for specialist-only workspace and appointment isolation."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, SimpleTestCase

from apps.appointments.views import _appointment_qs
from apps.dashboard.views import specialist_workspace
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

    @patch("apps.appointments.views.Appointment.scoped")
    def test_appointment_query_always_filters_to_own_profile(self, scoped):
        request = self.request()
        _appointment_qs(request)
        scoped.return_value.select_related.return_value.filter.assert_any_call(staff=self.profile)

    @patch("apps.appointments.views.Appointment.scoped")
    def test_missing_profile_returns_no_appointments(self, scoped):
        request = self.request()
        request.membership.staff_profile = None
        _appointment_qs(request)
        scoped.return_value.select_related.return_value.none.assert_called_once()

    @patch("apps.appointments.views.Appointment.scoped")
    def test_foreign_salon_profile_returns_no_appointments(self, scoped):
        request = self.request()
        request.membership.staff_profile = SimpleNamespace(
            pk=22, salon_id="salon-b", is_active=True, is_deleted=False
        )
        _appointment_qs(request)
        scoped.return_value.select_related.return_value.none.assert_called_once()

    def test_manager_cannot_open_private_specialist_workspace(self):
        request = self.request(role=SalonMembership.Role.MANAGER)
        with self.assertRaises(PermissionDenied):
            specialist_workspace.__wrapped__(request)
