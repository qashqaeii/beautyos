from django import forms
from django.utils.text import slugify

from apps.core.forms import PersianForm, PersianModelForm
from apps.salons.business_catalog import presets_for
from apps.salons.models import Salon, SalonSettings


class OnboardingBusinessTypeForm(PersianForm):
    business_type = forms.ChoiceField(
        label="نوع کسب‌وکار",
        choices=Salon.BusinessType.choices,
        widget=forms.RadioSelect,
    )


class OnboardingIdentityForm(PersianModelForm):
    slug = forms.SlugField(label="آدرس صفحه عمومی", max_length=140)

    class Meta:
        model = Salon
        fields = ["name", "slug", "logo", "public_phone", "city", "address", "tagline", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input-field"}),
            "public_phone": forms.TextInput(attrs={"class": "input-field"}),
            "city": forms.TextInput(attrs={"class": "input-field"}),
            "address": forms.Textarea(attrs={"class": "input-field", "rows": 2}),
            "tagline": forms.TextInput(attrs={"class": "input-field"}),
            "description": forms.Textarea(attrs={"class": "input-field", "rows": 3}),
            "logo": forms.ClearableFileInput(attrs={"class": "input-field"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].widget.attrs["class"] = "input-field"
        if self.instance and self.instance.pk and self.instance.slug:
            self.fields["slug"].initial = self.instance.slug

    def clean_slug(self):
        slug = self.cleaned_data["slug"]
        if not slug:
            slug = slugify(self.cleaned_data.get("name", ""), allow_unicode=False)
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
