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