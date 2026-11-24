from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

from apps.core.forms import PersianModelForm
from apps.services.models import Service, ServiceCategory


def service_category_queryset(salon, *, instance=None):
    qs = ServiceCategory.objects.filter(salon=salon, is_deleted=False, is_active=True)
    if instance and getattr(instance, "category_id", None):
        qs = ServiceCategory.objects.filter(salon=salon, is_deleted=False).filter(
            Q(is_active=True) | Q(pk=instance.category_id)
        )
    return qs.order_by("sort_order", "name")


class ServiceCategoryQuickForm(forms.Form):
    name = forms.CharField(max_length=80, label="نام دسته‌بندی")

    def __init__(self, *args, salon=None, **kwargs):
        self.salon = salon
        super().__init__(*args, **kwargs)
        self.fields["name"].widget.attrs.update({"class": "input-field", "autocomplete": "off"})

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if not name:
            raise ValidationError("نام دسته‌بندی را وارد کنید.")
        if not self.salon:
            raise ValidationError("سالن نامعتبر است.")
        if ServiceCategory.objects.filter(salon=self.salon, name=name, is_deleted=False).exists():
            raise ValidationError("این نام دسته‌بندی در این سالن قبلاً ثبت شده است.")
        return name

    def save(self):
        return ServiceCategory.objects.create(
            salon=self.salon,
            name=self.cleaned_data["name"],
        )


class ServiceCategoryForm(PersianModelForm):
    class Meta:
        model = ServiceCategory
        fields = ["name", "sort_order", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input-field"}),
            "sort_order": forms.NumberInput(attrs={"class": "input-field"}),
        }


class ServiceCreateForm(PersianModelForm):
    class Meta:
        model = Service
        fields = [
            "name",
            "category",
            "price_toman",
            "description",
            "is_active",
            "is_public",
            "image",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input-field"}),
            "description": forms.Textarea(attrs={"class": "input-field", "rows": 3}),
            "price_toman": forms.NumberInput(attrs={"class": "input-field"}),
            "category": forms.Select(attrs={"class": "input-field"}),
            "is_active": forms.CheckboxInput(attrs={"class": "rounded"}),
            "is_public": forms.CheckboxInput(attrs={"class": "rounded"}),
            "image": forms.FileInput(
                attrs={
                    "class": "service-form-file-native",
                    "accept": "image/*",
                    "x-ref": "serviceImage",
                    "@change": "imageName = $event.target.files?.[0]?.name || ''",
                }
            ),
        }

    def __init__(self, *args, salon=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].label = "نام خدمت"
        if salon:
            self.fields["category"].queryset = service_category_queryset(salon)
            self.fields["category"].empty_label = "—"


class ServiceForm(PersianModelForm):
    class Meta:
        model = Service
        fields = [
            "category",
            "name",
            "description",
            "duration_minutes",
            "price_toman",
            "sort_order",
            "is_active",
            "is_public",
            "image",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input-field"}),
            "description": forms.Textarea(attrs={"class": "input-field", "rows": 3}),
            "duration_minutes": forms.NumberInput(attrs={"class": "input-field"}),
            "price_toman": forms.NumberInput(attrs={"class": "input-field"}),
            "sort_order": forms.NumberInput(attrs={"class": "input-field"}),
            "category": forms.Select(attrs={"class": "input-field"}),
            "is_active": forms.CheckboxInput(attrs={"class": "rounded"}),
            "is_public": forms.CheckboxInput(attrs={"class": "rounded"}),
            "image": forms.FileInput(
                attrs={
                    "class": "service-form-file-native",
                    "accept": "image/*",
                    "x-ref": "serviceEditImage",
                    "@change": "editImageName = $event.target.files?.[0]?.name || ''",
                }
            ),
        }

    def __init__(self, *args, salon=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].label = "نام خدمت"
        if salon:
            self.fields["category"].queryset = service_category_queryset(salon, instance=self.instance)
