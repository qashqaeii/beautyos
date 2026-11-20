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
    for name in ("avatar","display_name","title","bio","is_active","is_bookable","calendar_color","services"):
        assert "{{ form."+name+" }}" in source
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
