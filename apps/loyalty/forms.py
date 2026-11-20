from django import forms

from apps.customers.models import Customer


class LoyaltyAdjustForm(forms.Form):
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.none(),
        label="مشتری",
        required=True,
    )
    points_delta = forms.IntegerField(
        label="تغییر امتیاز", min_value=-1000000, max_value=1000000,
        help_text="مثبت برای افزایش، منفی برای کاهش",
    )
    note = forms.CharField(
        label="توضیح",
        max_length=255,
        widget=forms.TextInput(attrs={"placeholder": "علت تغییر امتیاز"}),
    )

    def __init__(self, *, salon, **kwargs):
        super().__init__(**kwargs)
        self.fields["customer"].queryset = Customer.scoped(salon).filter(is_deleted=False).order_by(
            "full_name"
        )
        for field in self.fields.values():
            field.widget.attrs["class"]="input-field text-sm w-full"


from apps.core.fields import TomanAmountField
from apps.loyalty.models import LoyaltyPolicy


class LoyaltyPolicyForm(forms.Form):
    enabled = forms.BooleanField(label="فعال‌سازی امتیازدهی خودکار", required=False)
    spend_per_point_toman = TomanAmountField(label="مبلغ لازم برای یک امتیاز", min_value=1000, max_value=1000000000)
    visit_points = forms.IntegerField(label="امتیاز هر مراجعه انجام‌شده", min_value=0, max_value=10000)
    birthday_points = forms.IntegerField(label="هدیه امتیاز تولد سالانه", min_value=0, max_value=10000, required=False)
    referral_points = forms.IntegerField(label="پاداش معرفی مشتری جدید",min_value=0,max_value=10000,required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key in ("visit_points","birthday_points","referral_points"):
            self.fields[key].widget.attrs["class"]="input-field"

    def clean_birthday_points(self):
        return self.cleaned_data["birthday_points"] or 0

    def clean_referral_points(self):
        return self.cleaned_data["referral_points"] or 0
