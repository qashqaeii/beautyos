"""Regression guards for the shared Editorial Rose form-dialog contract."""
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODALS = sorted(
    path for path in (ROOT / "templates").glob("**/*_modal.html")
    if "inventory-create-modal-root" in path.read_text(encoding="utf-8")
)


@pytest.mark.parametrize("path", MODALS, ids=lambda path: path.stem)
def test_form_dialog_uses_shared_design_and_a11y(path):
    source = path.read_text(encoding="utf-8")
    assert 'class="inventory-create-modal-root luna-modal-root"' in source
    assert 'role="dialog"' in source
    assert 'aria-modal="true"' in source
    assert 'x-teleport="body"' in source
    assert "$dispatch('beautyos-close-" in source
    label = re.search(r'aria-labelledby="([^"]+)"', source).group(1)
    description = re.search(r'aria-describedby="([^"]+)"', source).group(1)
    assert f'id="{label}"' in source
    assert f'id="{description}"' in source
    assert 'class="luna-modal-heading"' in source
    assert 'tabindex="-1"' in source


def test_modal_family_includes_all_eleven_form_dialogs():
    assert len(MODALS) >= 11


def test_staff_profile_form_has_grouped_controls_and_native_upload():
    from apps.staff.forms import StaffProfileForm
    from apps.core.modal_widgets import ProfileImageWidget
    from django.forms import CheckboxSelectMultiple
    form = StaffProfileForm()
    assert isinstance(form.fields["avatar"].widget, ProfileImageWidget)
    assert isinstance(form.fields["services"].widget, CheckboxSelectMultiple)
    source=(ROOT / "templates/staff/partials/staff_edit_form.html").read_text(encoding="utf-8")
    for name in ("avatar","display_name","bio","is_active","is_bookable","calendar_color","services"):
        assert "{{ form."+name+" }}" in source
    assert 'type="hidden" name="title"' in source
    assert 'value="{{ form.title.value|default_if_none:' in source
    assert 'aria-controls="staff-specialty-options"' in source
    assert 'id="staff-specialty-options"' in source
    assert '$refs.specialtyTitle.value' in source
    assert 'enctype="multipart/form-data"' in source
    assert "luna-form-section" in source
    assert "luna-switch" in source
    assert "luna-service-section" in source


@pytest.mark.django_db
def test_staff_editor_upload_clear_and_service_selection(client, salon, owner_membership, settings, tmp_path):
    from io import BytesIO
    from PIL import Image
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.urls import reverse
    from apps.staff.models import StaffProfile
    from apps.services.models import Service

    settings.MEDIA_ROOT = tmp_path
    staff, _ = StaffProfile.objects.get_or_create(salon=salon, membership=owner_membership)
    service = Service.objects.create(salon=salon, name="خدمت نمونه")
    client.force_login(owner_membership.user)
    response = client.get(reverse("staff:detail", args=[staff.pk]), {"edit": "1"})
    assert response.status_code == 200
    assert 'data-luna-upload' in response.content.decode()
    buffer = BytesIO()
    Image.new("RGB", (12, 12), "#b99183").save(buffer, format="PNG")
    data = {"display_name": "متخصص نمونه", "title": "رنگ مو", "bio": "نمونه",
            "is_active": "on", "is_bookable": "on", "calendar_color": "",
            "services": [service.pk]}
    response = client.post(reverse("staff:edit", args=[staff.pk]), {
        **data, "avatar": SimpleUploadedFile("sample.png", buffer.getvalue(), content_type="image/png")})
    assert response.status_code == 302
    staff.refresh_from_db()
    assert staff.avatar and staff.services.filter(pk=service.pk).exists()
    response = client.get(reverse("staff:detail", args=[staff.pk]), {"edit": "1"})
    assert 'name="avatar-clear"' in response.content.decode()
    response = client.post(reverse("staff:edit", args=[staff.pk]), {**data, "avatar-clear": "on"})
    assert response.status_code == 302
    staff.refresh_from_db()
    assert not staff.avatar
    assert staff.services.filter(pk=service.pk).exists()


def test_image_upload_buttons_wrap_an_accessible_native_file_input():
    """Create/edit forms have one Persian chooser, never a second native file UI."""
    files = (
        "templates/customers/partials/customer_create_form.html",
        "templates/customers/form.html",
        "templates/services/partials/service_create_form.html",
        "templates/services/partials/service_edit_form.html",
    )
    for path in files:
        html = (ROOT / path).read_text(encoding="utf-8")
        cls = "customer-form-file__btn" if "customers/" in path else "service-form-file__btn"
        assert f'<label class="{cls}">' in html
        assert "<span>انتخاب تصویر</span>" in html
        assert f'<button type="button" class="{cls}"' not in html
        assert '@click="$refs.customerAvatar.click()"' not in html
        assert '@click="$refs.serviceImage.click()"' not in html
        assert '@click="$refs.serviceEditImage.click()"' not in html
    css = (ROOT / "static/css/luna-modals.css").read_text(encoding="utf-8")
    assert '.customer-form-file__btn > input[type="file"]' in css
    assert '.service-form-file__btn > input[type="file"]' in css
    assert "clip-path: inset(50%) !important" in css
    assert "display: block !important" in css
    assert ":focus-within" in css


@pytest.mark.django_db
def test_customer_and_service_modals_keep_file_upload_inputs(client, owner_membership, salon):
    from apps.services.models import Service
    from django.urls import reverse

    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.pk)
    session.save()
    service = Service.objects.create(salon=salon, name="رنگ مو")
    for route, query in (
        ("customers:list", {"create": "1"}),
        ("services:list", {"create": "1"}),
        ("services:list", {"edit": str(service.pk)}),
    ):
        response = client.get(reverse(route), query)
        assert response.status_code == 200
        html = response.content.decode()
        assert 'type="file"' in html
        assert "انتخاب تصویر" in html
        assert 'enctype="multipart/form-data"' in html


def test_shared_profile_image_widget_keeps_its_custom_chooser():
    from apps.core.modal_widgets import ProfileImageWidget
    from apps.staff.forms import StaffProfileForm
    from apps.customers.forms import CustomerForm

    for form in (StaffProfileForm(), CustomerForm()):
        widget = form.fields["avatar"].widget
        assert isinstance(widget, ProfileImageWidget)
        html = str(widget.render("avatar", None, attrs={"id": "id_avatar"}))
        assert 'class="luna-upload__button"' in html
        assert "انتخاب تصویر" in html
        assert 'type="file"' in html
