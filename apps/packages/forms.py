from django import forms
from django.utils import timezone

from apps.core.fields import TomanAmountField
from apps.core.forms import PersianForm, PersianModelForm
from apps.customers.models import Customer
from apps.packages.models import CustomerPackage, ServicePackage


class ServicePackageForm(PersianModelForm):
    class Meta:
        model = ServicePackage
        fields = ["name", "description", "price_toman", "session_count", "validity_days", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input-field"}),
            "description": forms.Textarea(attrs={"class": "input-field", "rows": 3}),
            "session_count": forms.NumberInput(attrs={"class": "input-field"}),
            "validity_days": forms.NumberInput(attrs={"class": "input-field"}),
            "is_active": forms.CheckboxInput(attrs={"class": "rounded border-line"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["session_count"].min_value = 1
        self.fields["validity_days"].min_value = 1
        self.fields["validity_days"].max_value = 36500
        self.fields["price_toman"] = TomanAmountField(
            label="قیمت",
            min_value=1,
            max_value=2**63 - 1,
            error_messages={
                "required": "قیمت پکیج را وارد کنید.",
                "min_value": "قیمت باید حداقل ۱ تومان باشد.",
                "invalid": "مبلغ نامعتبر است. فقط عدد تومان با جداکنندهٔ هزارگان وارد کنید.",
            },
        )


class SellPackageForm(PersianForm):
    customer = forms.ModelChoiceField(queryset=Customer.objects.none(), widget=forms.Select(attrs={"class": "input-field"}))
    package = forms.ModelChoiceField(queryset=ServicePackage.objects.none(), widget=forms.Select(attrs={"class": "input-field"}))

    def __init__(self, *args, salon=None, **kwargs):
        super().__init__(*args, **kwargs)
        if salon:
            self.fields["customer"].queryset = Customer.scoped(salon).filter(is_deleted=False)
            self.fields["package"].queryset = ServicePackage.scoped(salon).filter(is_active=True)

    def save(self, salon):
        package = self.cleaned_data["package"]
        from datetime import timedelta

        expires = timezone.now() + timedelta(days=package.validity_days)
        return CustomerPackage.objects.create(
            salon=salon,
            customer=self.cleaned_data["customer"],
            package=package,
            sessions_total=package.session_count,
            price_paid_toman=package.price_toman,
            expires_at=expires,
        )
