from django import forms

from apps.customers.models import Customer


class LoyaltyAdjustForm(forms.Form):
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.none(),
        label="مشتری",
        required=True,
    )
    points_delta = forms.IntegerField(
        label="تغییر امتیاز",
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
        self.fields["customer"].widget.attrs.update({"class": "input-field text-sm w-full"})
