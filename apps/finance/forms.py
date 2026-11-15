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

            self.fields["appointment"].queryset = Appointment.scoped(salon).order_by("-start_at")[:200]
            self.fields["appointment"].required = False


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


class SalonDebtPaymentForm(PersianForm):
    amount_toman = forms.IntegerField(min_value=1, widget=forms.NumberInput(attrs={"class": "input-field"}))
    note = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "input-field"}))
