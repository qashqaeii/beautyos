from django import forms
from django.core.exceptions import ValidationError
from django.utils.text import slugify

from apps.core.forms import PersianModelForm
from apps.salons.models import Salon, SalonSettings

LOGO_MAX_BYTES = 2 * 1024 * 1024
LOGO_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


class SalonProfileForm(PersianModelForm):
    slug = forms.CharField(
        label="آدرس صفحه عمومی",
        max_length=140,
        widget=forms.TextInput(attrs={"class": "input-field", "dir": "ltr"}),
    )
    clear_logo = forms.BooleanField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Salon
        fields = [
            "name",
            "tagline",
            "description",
            "public_phone",
            "address",
            "city",
            "instagram",
            "whatsapp",
            "is_accepting_bookings",
            "is_active",
            "logo",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input-field"}),
            "tagline": forms.TextInput(attrs={"class": "input-field"}),
            "description": forms.Textarea(attrs={"class": "input-field", "rows": 3}),
            "public_phone": forms.TextInput(
                attrs={"class": "input-field input-field--tel", "type": "tel", "dir": "ltr", "inputmode": "tel"}
            ),
            "address": forms.Textarea(attrs={"class": "input-field", "rows": 2}),
            "city": forms.TextInput(attrs={"class": "input-field"}),
            "instagram": forms.TextInput(attrs={"class": "input-field", "dir": "ltr"}),
            "whatsapp": forms.TextInput(attrs={"class": "input-field input-field--tel", "type": "tel", "dir": "ltr"}),
            "is_accepting_bookings": forms.CheckboxInput(attrs={"class": "rounded"}),
            "is_active": forms.CheckboxInput(attrs={"class": "rounded"}),
            "logo": forms.ClearableFileInput(attrs={"class": "input-field"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["is_accepting_bookings"].label = "پذیرش رزرو آنلاین"
        self.fields["is_active"].label = "سالن فعال است"
        if self.instance and self.instance.pk and not self.is_bound:
            self.fields["slug"].initial = self.instance.slug

    def clean_slug(self):
        raw = (self.cleaned_data.get("slug") or "").strip()
        slug = slugify(raw, allow_unicode=False)
        if not slug:
            slug = slugify(self.instance.name or "", allow_unicode=False)
        if not slug:
            raise forms.ValidationError("آدرس صفحه معتبر نیست.")
        qs = Salon.objects.filter(slug=slug)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("این آدرس قبلاً استفاده شده است.")
        return slug

    def clean_logo(self):
        logo = self.cleaned_data.get("logo")
        if not logo or not hasattr(logo, "content_type"):
            return logo
        if logo.size > LOGO_MAX_BYTES:
            raise ValidationError("حداکثر حجم لوگو ۲ مگابایت است.")
        content_type = getattr(logo, "content_type", "") or ""
        if content_type and content_type not in LOGO_ALLOWED_CONTENT_TYPES:
            raise ValidationError("فرمت مجاز: JPG، PNG یا WebP.")
        return logo

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.slug = self.cleaned_data["slug"]
        if self.cleaned_data.get("clear_logo"):
            if instance.logo:
                instance.logo.delete(save=False)
            instance.logo = None
        if commit:
            instance.save()
        return instance


class SalonSettingsForm(PersianModelForm):
    """Legacy aggregate form — prefer SalonProfileForm for profile UI."""

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