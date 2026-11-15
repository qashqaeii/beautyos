import pytest

from apps.appointments.forms import AppointmentForm
from apps.appointments.picker_context import resolve_customer_picker_context


@pytest.mark.django_db
def test_resolve_customer_picker_new_mode_without_checkbox(owner_membership, salon):
    form = AppointmentForm(
        salon=salon,
        membership=owner_membership,
        data={
            "new_customer_first_name": "م",
            "new_customer_last_name": "ن",
            "new_customer_phone": "09121111222",
        },
    )
    ctx = resolve_customer_picker_context(form=form, membership=owner_membership, salon=salon)
    assert ctx["picker_initial_mode"] == "new"


@pytest.mark.django_db
def test_picker_context_prefers_new_over_search_noise(owner_membership, salon):
    """customer_search without selection must not hide new-customer panel after validation error."""
    form = AppointmentForm(
        salon=salon,
        membership=owner_membership,
        data={
            "customer_search": "0912",
            "new_customer_first_name": "رضا",
            "new_customer_last_name": "تست",
            "new_customer_phone": "09123334455",
        },
    )
    ctx = resolve_customer_picker_context(form=form, membership=owner_membership, salon=salon)
    assert ctx["picker_initial_mode"] == "new"
    assert ctx["customer_picker_config"]["initialMode"] == "new"