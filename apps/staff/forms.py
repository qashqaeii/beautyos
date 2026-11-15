from datetime import time

from django import forms
from django.core.exceptions import ValidationError

from apps.core.forms import PersianForm, PersianModelForm
from apps.core.widgets import JalaliDateWidget
from apps.core.utils.phone import normalize_iran_mobile
from apps.services.models import Service
from apps.staff.fields import HHmmTimeField
from apps.staff.calendar_colors import CALENDAR_COLOR_CHOICES, normalize_calendar_color
from apps.staff.models import StaffProfile, StaffTimeOff, StaffWorkHours


class StaffInviteForm(PersianForm):
    first_name = forms.CharField(
        label="نام",
        max_length=60,
        widget=forms.TextInput(attrs={"class": "input-field", "autocomplete": "given-name"}),
    )
    last_name = forms.CharField(
        label="نام خانوادگی",
        max_length=60,
        widget=forms.TextInput(attrs={"class": "input-field", "autocomplete": "family-name"}),
    )
    specialty = forms.CharField(
        label="تخصص",
        max_length=80,
        widget=forms.TextInput(attrs={"class": "input-field"}),
    )
    phone = forms.CharField(
        label="شماره موبایل",
        widget=forms.TextInput(
            attrs={
                "class": "input-field input-field--tel",
                "type": "tel",
                "inputmode": "tel",
                "dir": "ltr",
                "autocomplete": "tel",
            }
        ),
    )

    def clean_first_name(self):
        value = (self.cleaned_data.get("first_name") or "").strip()
        if not value:
            raise ValidationError("نام را وارد کنید.")
        return value

    def clean_last_name(self):
        value = (self.cleaned_data.get("last_name") or "").strip()
        if not value:
            raise ValidationError("نام خانوادگی را وارد کنید.")
        return value

    def clean_specialty(self):
        value = (self.cleaned_data.get("specialty") or "").strip()
        if not value:
            raise ValidationError("تخصص را وارد کنید.")
        return value

    def clean_phone(self):
        raw = self.cleaned_data.get("phone") or ""
        try:
            return normalize_iran_mobile(raw)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc


class StaffProfileForm(PersianModelForm):
    class Meta:
        model = StaffProfile
        fields = [
            "display_name",
            "title",
            "bio",
            "avatar",
            "is_bookable",
            "is_active",
            "calendar_color",
            "services",
        ]
        widgets = {
            "display_name": forms.TextInput(attrs={"class": "input-field"}),
            "title": forms.TextInput(attrs={"class": "input-field"}),
            "bio": forms.Textarea(attrs={"class": "input-field", "rows": 3}),
            "avatar": forms.ClearableFileInput(attrs={"class": "input-field", "accept": "image/*"}),
            "services": forms.SelectMultiple(attrs={"class": "input-field"}),
            "calendar_color": forms.RadioSelect(attrs={"class": "staff-calendar-color-picker"}),
        }

    def __init__(self, *args, salon=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.salon = salon
        self.fields["avatar"].label = "عکس پروفایل"
        self.fields["avatar"].required = False
        self.fields["calendar_color"].label = "رنگ تقویم"
        self.fields["calendar_color"].required = False
        self.fields["calendar_color"].choices = CALENDAR_COLOR_CHOICES
        if salon:
            self.fields["services"].queryset = Service.scoped(salon).filter(is_active=True, is_deleted=False)

    def clean_calendar_color(self):
        raw = self.cleaned_data.get("calendar_color") or ""
        if not raw:
            return ""
        color = normalize_calendar_color(raw)
        if not color:
            raise ValidationError("رنگ نامعتبر است.")
        return color

    def clean(self):
        cleaned = super().clean()
        color = cleaned.get("calendar_color") or ""
        if color and self.salon and self.instance and self.instance.pk:
            duplicate = (
                StaffProfile.scoped(self.salon)
                .filter(is_deleted=False, calendar_color=color)
                .exclude(pk=self.instance.pk)
                .exists()
            )
            if duplicate:
                self.add_error("calendar_color", "این رنگ قبلاً برای متخصص دیگری ثبت شده است.")
        return cleaned


class WorkHoursForm(PersianModelForm):
    start_time = HHmmTimeField(label="ساعت شروع", required=False)
    end_time = HHmmTimeField(label="ساعت پایان", required=False)
    reference_date = forms.DateField(
        label="تاریخ",
        required=False,
        help_text="روز هفته از روی این تاریخ مشخص می‌شود.",
    )

    class Meta:
        model = StaffWorkHours
        fields = ["weekday", "start_time", "end_time", "is_closed"]
        widgets = {
            "weekday": forms.Select(attrs={"class": "input-field"}),
            "is_closed": forms.CheckboxInput(attrs={"class": "rounded"}),
        }

    def __init__(self, *args, week_anchor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["is_closed"].label = "این روز تعطیل است"
        if week_anchor and not self.is_bound:
            self.fields["reference_date"].initial = week_anchor

    def clean(self):
        cleaned = super().clean()
        reference = cleaned.get("reference_date")
        if reference:
            from apps.core.utils.dates import staff_weekday_for_date

            cleaned["weekday"] = staff_weekday_for_date(reference)
        is_closed = cleaned.get("is_closed")
        start = cleaned.get("start_time")
        end = cleaned.get("end_time")

        if is_closed:
            cleaned["start_time"] = time(0, 0)
            cleaned["end_time"] = time(0, 0)
            return cleaned

        if start is None:
            self.add_error("start_time", ValidationError("ساعت شروع را وارد کنید."))
        if end is None:
            self.add_error("end_time", ValidationError("ساعت پایان را وارد کنید."))
        if self.errors:
            return cleaned

        if end <= start:
            self.add_error("end_time", ValidationError("ساعت پایان باید بعد از ساعت شروع باشد."))
        return cleaned


class StaffTimeOffForm(PersianModelForm):
    class Meta:
        model = StaffTimeOff
        fields = ["start_date", "end_date", "reason"]
        widgets = {
            "reason": forms.Textarea(
                attrs={
                    "class": "input-field staff-timeoff-reason-input",
                    "rows": 3,
                    "placeholder": "توضیح کوتاه (اختیاری)",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["start_date"].widget = JalaliDateWidget(
            attrs={
                "class": "input-field",
                "aria-label": "تاریخ شروع",
                "placeholder": "۱۴۰۵/۰۸/۲۱",
            },
            show_calendar_icon=False,
        )
        self.fields["end_date"].widget = JalaliDateWidget(
            attrs={
                "class": "input-field",
                "aria-label": "تاریخ پایان",
                "placeholder": "۱۴۰۵/۰۸/۲۱",
            },
            show_calendar_icon=False,
        )
        self.fields["reason"].label = "علت مرخصی"

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "تاریخ پایان نمی‌تواند قبل از تاریخ شروع باشد.")
        return cleaned
