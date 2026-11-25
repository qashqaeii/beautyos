from django import forms
from django.utils import timezone
import jdatetime
from apps.core.utils.money import format_toman_fa

from apps.core.forms import PersianForm, PersianModelForm
from apps.customers.models import Customer
from apps.finance.models import Payment, SalonDebt


class PaymentAppointmentSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        appointment = getattr(value, "instance", None)
        if appointment is not None:
            option["attrs"].update({"data-customer": str(appointment.customer_id), "data-balance": str(self.balances[appointment.pk])})
        return option


class PaymentForm(PersianModelForm):
    payment_kind = forms.ChoiceField(choices=[("service", "پرداخت هزینه خدمت"), ("deposit", "ثبت بیعانه")], required=False, initial="service", widget=forms.RadioSelect)
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
            "appointment": PaymentAppointmentSelect(attrs={"class": "input-field"}),
            "total_amount_toman": forms.TextInput(attrs={"class": "input-field", "inputmode": "numeric", "data-payment-money": "true"}),
            "discount_toman": forms.TextInput(attrs={"class": "input-field", "inputmode": "numeric", "data-payment-money": "true"}),
            "paid_amount_toman": forms.TextInput(attrs={"class": "input-field", "inputmode": "numeric", "data-payment-money": "true"}),
            "method": forms.Select(attrs={"class": "input-field"}),
            "status": forms.Select(attrs={"class": "input-field"}),
            "notes": forms.Textarea(attrs={"class": "input-field", "rows": 2}),
        }

    def __init__(self, *args, salon=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].choices = [(v, label) for v, label in Payment.Status.choices if v != Payment.Status.REFUNDED]
        self.fields["total_amount_toman"].label = "مبلغ قابل پرداخت پیش از تخفیف"
        if salon:
            self.fields["customer"].queryset = Customer.scoped(salon).filter(is_deleted=False)
            from apps.appointments.models import Appointment

            from apps.dashboard.role_services import appointment_payment_summary
            candidates = Appointment.scoped(salon).exclude(
                status__in=(Appointment.Status.CANCELLED, Appointment.Status.NO_SHOW)
            ).filter(price_toman__gt=0, customer__is_deleted=False).select_related(
                "service", "staff", "package_use"
            ).prefetch_related("payments__refunds").order_by("-start_at", "-pk")
            balances = {}
            labels = {}
            for appointment in candidates:
                balance = appointment_payment_summary(appointment)["owed_toman"]
                if balance <= 0:
                    continue
                balances[appointment.pk] = balance
                day = jdatetime.date.fromgregorian(date=timezone.localtime(appointment.start_at).date()).strftime("%Y/%m/%d")
                labels[appointment.pk] = f"{appointment.service.name} | {appointment.staff.display_name} | {day} | مانده {format_toman_fa(balance)} تومان"
            field = self.fields["appointment"]
            field.queryset = candidates.filter(pk__in=balances)
            field.widget.balances = balances
            field.label_from_instance = lambda appointment: labels[appointment.pk]
            field.label = "خدمت قابل پرداخت"
            field.empty_label = "انتخاب نوبت (برای بیعانه اختیاری)"
            field.required = False

    def clean(self):
        data = super().clean()
        appointment = data.get("appointment")
        kind = data.get("payment_kind") or "service"
        if self.data.get("payment_kind") == "service" and not appointment:
            self.add_error("appointment", "برای پرداخت هزینه خدمت، نوبت را انتخاب کنید.")
        if kind == "deposit":
            if not data.get("paid_amount_toman") or data.get("discount_toman") != 0:
                self.add_error("paid_amount_toman", "بیعانه باید مبلغ مثبت و بدون تخفیف باشد.")
            if not appointment and data.get("total_amount_toman") != data.get("paid_amount_toman"):
                self.add_error("total_amount_toman", "مبلغ بیعانه و دریافتی باید برابر باشند.")
        customer = data.get("customer")
        if appointment and customer and appointment.customer_id != customer.pk:
            self.add_error("appointment", "نوبت انتخاب‌شده متعلق به این مشتری نیست.")
        if appointment and data.get("total_amount_toman") is not None and data["total_amount_toman"] != self.fields["appointment"].widget.balances.get(appointment.pk):
            self.add_error("total_amount_toman", "مبلغ باید برابر مانده خدمت انتخاب‌شده باشد.")
        for field in ("total_amount_toman", "discount_toman", "paid_amount_toman"):
            value = data.get(field)
            if value is not None and value < 0:
                self.add_error(field, "مبلغ نمی‌تواند منفی باشد.")
        total, discount, paid = (data.get(k) for k in ("total_amount_toman", "discount_toman", "paid_amount_toman"))
        if None not in (total, discount, paid) and min(total, discount, paid) >= 0:
            if discount > total:
                self.add_error("discount_toman", "تخفیف نمی‌تواند از مبلغ کل بیشتر باشد.")
            elif paid > total - discount:
                self.add_error("paid_amount_toman", "پرداخت نمی‌تواند بیشتر از مبلغ پس از تخفیف باشد.")
            else:
                net = total - discount
                expected = Payment.Status.PAID if paid == net else Payment.Status.PARTIAL if paid > 0 else Payment.Status.PENDING
                if data.get("status") and data["status"] != expected:
                    self.add_error("status", "وضعیت پرداخت با مبلغ دریافتی و مانده مطابقت ندارد.")
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
