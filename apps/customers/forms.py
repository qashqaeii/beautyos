from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.forms import PersianModelForm
from apps.core.widgets import JalaliDateWidget
from apps.core.utils.phone import normalize_iran_mobile
from apps.customers.models import Customer, CustomerNote, CustomerTag


def _customer_birth_date_widget() -> JalaliDateWidget:
    return JalaliDateWidget(
        attrs={
            "class": "input-field",
            "aria-label": "تاریخ تولد",
            "placeholder": "۱۴۰۵/۰۸/۲۱",
        },
        show_calendar_icon=True,
        variant="birth",
        max_iso="today",
    )


def _validate_birth_date_not_future(value):
    if value and value > timezone.localdate():
        raise ValidationError("تاریخ تولد نمی‌تواند در آینده باشد.")
    return value


class CustomerCreateForm(PersianModelForm):
    phone_input = forms.CharField(label="شماره موبایل", max_length=20)

    class Meta:
        model = Customer
        fields = ["full_name", "birth_date", "is_vip", "marketing_consent", "avatar"]
        widgets = {
            "full_name": forms.TextInput(attrs={"class": "input-field"}),
            "birth_date": forms.DateInput(attrs={"class": "input-field"}),
            "is_vip": forms.CheckboxInput(attrs={"class": "rounded"}),
            "marketing_consent": forms.CheckboxInput(attrs={"class": "rounded"}),
            "avatar": forms.FileInput(
                attrs={
                    "class": "customer-form-file-native",
                    "accept": "image/*",
                    "x-ref": "customerAvatar",
                    "@change": "imageName = $refs.customerAvatar?.files?.[0]?.name || ''; imagePreview = $refs.customerAvatar?.files?.[0] ? URL.createObjectURL($refs.customerAvatar.files[0]) : ''",
                }
            ),
        }

    def __init__(self, *args, salon=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.salon = salon
        self.fields["phone_input"].widget.attrs.update(
            {
                "class": "input-field input-field--tel",
                "type": "tel",
                "inputmode": "tel",
                "dir": "ltr",
                "autocomplete": "tel",
            }
        )
        self.fields["marketing_consent"].initial = False
        self.fields["avatar"].label = "تصویر پروفایل"
        self.fields["avatar"].required = False
        self.fields["birth_date"].widget = _customer_birth_date_widget()

    def clean_birth_date(self):
        return _validate_birth_date_not_future(self.cleaned_data.get("birth_date"))

    def clean_phone_input(self):
        try:
            return normalize_iran_mobile(self.cleaned_data["phone_input"])
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.phone = self.cleaned_data["phone_input"]
        instance.salon = self.salon
        instance.status = Customer.Status.NEW
        if commit:
            instance.save()
        return instance


class CustomerForm(PersianModelForm):
    phone_input = forms.CharField(label="شماره موبایل", max_length=20)

    class Meta:
        model = Customer
        fields = [
            "full_name",
            "email",
            "birth_date",
            "is_vip",
            "status",
            "tags",
            "marketing_consent",
            "avatar",
        ]
        widgets = {
            "full_name": forms.TextInput(attrs={"class": "input-field"}),
            "email": forms.EmailInput(attrs={"class": "input-field"}),
            "birth_date": forms.DateInput(attrs={"class": "input-field"}),
            "status": forms.Select(attrs={"class": "input-field"}),
            "tags": forms.SelectMultiple(attrs={"class": "input-field"}),
            "marketing_consent": forms.CheckboxInput(attrs={"class": "rounded border-aubergine/20"}),
            "is_vip": forms.CheckboxInput(attrs={"class": "rounded border-aubergine/20"}),
        }

    def __init__(self, *args, salon=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.salon = salon
        if salon:
            self.fields["tags"].queryset = CustomerTag.objects.filter(salon=salon)
        if self.instance.pk:
            from apps.core.utils.phone import display_iran_mobile

            self.fields["phone_input"].initial = display_iran_mobile(self.instance.phone)
        self.fields["phone_input"].widget.attrs.update({"class": "input-field", "inputmode": "tel"})
        self.fields["birth_date"].widget = _customer_birth_date_widget()

    def clean_birth_date(self):
        return _validate_birth_date_not_future(self.cleaned_data.get("birth_date"))

    def clean_phone_input(self):
        try:
            return normalize_iran_mobile(self.cleaned_data["phone_input"])
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.phone = self.cleaned_data["phone_input"]
        instance.salon = self.salon
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class CustomerNoteForm(PersianModelForm):
    class Meta:
        model = CustomerNote
        fields = ["body"]
        widgets = {"body": forms.Textarea(attrs={"class": "input-field", "rows": 3, "placeholder": "یادداشت داخلی..."})}


class CustomerTagForm(PersianModelForm):
    class Meta:
        model = CustomerTag
        fields = ["name", "color"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input-field"}),
            "color": forms.TextInput(attrs={"class": "input-field", "type": "color"}),
        }
