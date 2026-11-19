from django import forms

from apps.core.forms import PersianForm, PersianModelForm
from apps.customers.models import Customer
from apps.finance.models import Payment, SalonDebt


class PaymentForm(PersianModelForm):
    class Meta:
        model = Payment
        fields = [
            "customer",
            "appointment",
            "total_amount_toman",
            "discount_toman",
            "paid_amount_toman",
            "method",
            "status",
            "notes",
        ]
        widgets = {
            "customer": forms.Select(attrs={"class": "input-field"}),
            "appointment": forms.Select(attrs={"class": "input-field"}),
            "total_amount_toman": forms.NumberInput(attrs={"class": "input-field"}),
            "discount_toman": forms.NumberInput(attrs={"class": "input-field"}),
            "paid_amount_toman": forms.NumberInput(attrs={"class": "input-field"}),
            "method": forms.Select(attrs={"class": "input-field"}),
            "status": forms.Select(attrs={"class": "input-field"}),
            "notes": forms.Textarea(attrs={"class": "input-field", "rows": 2}),
        }

    def __init__(self, *args, salon=None, **kwargs):
        super().__init__(*args, **kwargs)
        if salon:
            self.fields["customer"].queryset = Customer.scoped(salon).filter(is_deleted=False)
            from apps.appointments.models import Appointment

            recent = Appointment.scoped(salon).order_by("-start_at", "-pk").values("pk")[:200]
            # ModelChoiceField validation calls queryset.get(); the outer query must not be sliced.
            self.fields["appointment"].queryset = Appointment.scoped(salon).filter(pk__in=recent).order_by("-start_at", "-pk")
            self.fields["appointment"].required = False

    def clean(self):
        data = super().clean()
        appointment = data.get("appointment")
        customer = data.get("customer")
        if appointment and customer and appointment.customer_id != customer.pk:
            self.add_error("appointment", "نوبت انتخاب‌شده متعلق به این مشتری نیست.")
        for field in ("total_amount_toman", "discount_toman", "paid_amount_toman"):
            value = data.get(field)
            if value is not None and value < 0:
                self.add_error(field, "مبلغ نمی‌تواند منفی باشد.")
        return data


class SalonDebtForm(PersianModelForm):
    class Meta:
        model = SalonDebt
        fields = ["creditor_name", "creditor_type", "principal_toman", "due_date", "note"]
        widgets = {
            "creditor_name": forms.TextInput(attrs={"class": "input-field"}),
            "creditor_type": forms.Select(attrs={"class": "input-field"}),
            "principal_toman": forms.NumberInput(attrs={"class": "input-field"}),
            "due_date": forms.DateInput(attrs={"class": "input-field"}),
            "note": forms.Textarea(attrs={"class": "input-field", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["due_date"].required = False
        self.fields["note"].required = False

    def clean_principal_toman(self):
        value = self.cleaned_data["principal_toman"]
        if value <= 0:
            raise forms.ValidationError("مبلغ بدهی باید بزرگ‌تر از صفر باشد.")
        return value


class SalonDebtPaymentForm(PersianForm):
    amount_toman = forms.IntegerField(min_value=1, max_value=2**63 - 1, widget=forms.NumberInput(attrs={"class": "input-field"}))
    note = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "input-field"}))
