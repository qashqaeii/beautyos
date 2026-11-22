from uuid import uuid4

from django import forms
from django.utils.text import slugify

from apps.core.forms import PersianForm, PersianModelForm
from apps.salons.business_catalog import presets_for
from apps.salons.models import Salon, SalonSettings
from apps.services.models import Service
from apps.staff.models import StaffProfile


class OnboardingBusinessTypeForm(PersianForm):
    name = forms.CharField(
        label="نام سالن",
        max_length=120,
        widget=forms.TextInput(attrs={"class": "input-field", "autocomplete": "organization"}),
    )
    def clean_name(self):
        value = (self.cleaned_data.get("name") or "").strip()
        if not value:
            raise forms.ValidationError("نام سالن را وارد کنید.")
        return value


class OnboardingIdentityForm(PersianModelForm):
    slug = forms.SlugField(label="آدرس صفحه عمومی", max_length=140, required=False)

    class Meta:
        model = Salon
        fields = ["slug", "logo", "public_phone", "city", "address", "tagline", "description"]
        widgets = {
            "public_phone": forms.TextInput(attrs={"class": "input-field", "type": "tel", "dir": "ltr"}),
            "city": forms.TextInput(attrs={"class": "input-field"}),
            "address": forms.Textarea(attrs={"class": "input-field", "rows": 2}),
            "tagline": forms.TextInput(attrs={"class": "input-field"}),
            "description": forms.Textarea(attrs={"class": "input-field", "rows": 3}),
            "logo": forms.ClearableFileInput(attrs={"class": "input-field"}),
        }

    def __init__(self, *args, salon_name="", **kwargs):
        super().__init__(*args, **kwargs)
        self.salon_name = (salon_name or "").strip()
        self.fields["slug"].widget.attrs["class"] = "input-field"
        if self.instance and self.instance.pk and self.instance.slug:
            self.fields["slug"].initial = self.instance.slug
        elif self.salon_name and not (self.instance and self.instance.pk):
            self.fields["slug"].initial = (
                slugify(self.salon_name, allow_unicode=False)
                or f"salon-{uuid4().hex[:8]}"
            )

    def clean_slug(self):
        slug = (self.cleaned_data.get("slug") or "").strip()
        if not slug:
            if self.instance and self.instance.pk and self.instance.slug:
                slug = self.instance.slug
            else:
                slug = slugify(self.salon_name, allow_unicode=False) or f"salon-{uuid4().hex[:8]}"
        qs = Salon.objects.filter(slug=slug)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("این آدرس قبلاً استفاده شده است.")
        return slug


class OnboardingThemeForm(PersianForm):
    dashboard_theme = forms.ChoiceField(
        label="تم پنل مدیریت",
        choices=SalonSettings.DashboardTheme.choices,
        widget=forms.RadioSelect,
    )
    public_theme = forms.ChoiceField(
        label="قالب صفحه عمومی",
        choices=Salon.PublicTheme.choices,
        widget=forms.RadioSelect,
    )


class OnboardingServiceSetupForm(PersianForm):
    selected_presets = forms.MultipleChoiceField(
        label="خدمات پیشنهادی",
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, salon=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.salon = salon
        presets = presets_for(salon.business_type) if salon else []
        self.fields["selected_presets"].choices = [(str(i), p["name"]) for i, p in enumerate(presets)]

    def cleaned_custom_services(self):
        rows = []
        if not self.data:
            return rows
        names = self.data.getlist("custom_name")
        durations = self.data.getlist("custom_duration")
        prices = self.data.getlist("custom_price")
        for name, duration, price in zip(names, durations, prices):
            if not (name or "").strip():
                continue
            rows.append({"name": name.strip(), "duration_minutes": duration, "price_toman": price})
        return rows

    def clean(self):
        cleaned = super().clean()
        cleaned["custom_services"] = self.cleaned_custom_services()
        return cleaned


class OnboardingStaffForm(PersianModelForm):
    class Meta:
        model = StaffProfile
        fields = ["display_name", "title", "is_bookable"]
        widgets = {
            "display_name": forms.TextInput(attrs={"class": "input-field"}),
            "title": forms.TextInput(attrs={"class": "input-field"}),
            "is_bookable": forms.CheckboxInput(attrs={"class": "rounded"}),
        }

    services = forms.ModelMultipleChoiceField(
        label="خدمات قابل ارائه",
        required=False,
        queryset=Service.objects.none(),
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, salon=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["is_bookable"].label = "قابل رزرو در نوبت‌دهی"
        if salon:
            self.fields["services"].queryset = Service.scoped(salon).filter(is_deleted=False, is_active=True)
        if self.instance and self.instance.pk and not self.is_bound:
            self.fields["services"].initial = self.instance.services.all()

    def save(self, commit=True):
        profile = super().save(commit=commit)
        if commit:
            profile.services.set(self.cleaned_data.get("services") or [])
        return profile
