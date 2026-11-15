from django import forms

from apps.core.forms import PersianModelForm
from apps.salons.models import Salon, SalonSettings


class SalonSettingsForm(PersianModelForm):
    class Meta:
        model = Salon
        fields = [
            "name",
            "tagline",
            "description",
            "public_phone",
            "address",
            "city",
            "public_theme",
            "logo",
            "cover_image",
            "instagram",
            "whatsapp",
            "is_accepting_bookings",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input-field"}),
            "tagline": forms.TextInput(attrs={"class": "input-field"}),
            "description": forms.Textarea(attrs={"class": "input-field", "rows": 4}),
            "public_phone": forms.TextInput(attrs={"class": "input-field", "inputmode": "tel"}),
            "address": forms.Textarea(attrs={"class": "input-field", "rows": 2}),
            "city": forms.TextInput(attrs={"class": "input-field"}),
            "public_theme": forms.Select(attrs={"class": "input-field"}),
            "instagram": forms.TextInput(attrs={"class": "input-field"}),
            "whatsapp": forms.TextInput(attrs={"class": "input-field"}),
            "is_accepting_bookings": forms.CheckboxInput(attrs={"class": "rounded"}),
        }


class SalonDashboardThemeForm(PersianModelForm):
    class Meta:
        model = SalonSettings
        fields = ["dashboard_theme"]
        widgets = {
            "dashboard_theme": forms.RadioSelect(attrs={"class": "theme-radio"}),
        }


class SalonRetentionSettingsForm(PersianModelForm):
    class Meta:
        model = SalonSettings
        fields = [
            "retention_days_30",
            "retention_days_60",
            "retention_days_90",
            "booking_lead_time_minutes",
            "cancellation_notice_hours",
        ]
        widgets = {
            "retention_days_30": forms.NumberInput(attrs={"class": "input-field"}),
            "retention_days_60": forms.NumberInput(attrs={"class": "input-field"}),
            "retention_days_90": forms.NumberInput(attrs={"class": "input-field"}),
            "booking_lead_time_minutes": forms.NumberInput(attrs={"class": "input-field"}),
            "cancellation_notice_hours": forms.NumberInput(attrs={"class": "input-field"}),
        }
