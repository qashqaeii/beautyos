from django import forms

from apps.commissions.models import CommissionRule
from apps.core.fields import TomanAmountField
from apps.core.forms import PersianForm, PersianModelForm
from apps.staff.models import StaffProfile


class CommissionRuleForm(PersianModelForm):
    def __init__(self, *args, salon=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.salon = salon
        if salon:
            from apps.services.models import Service

            self.fields["staff"].queryset = StaffProfile.scoped(salon).filter(is_active=True)
            self.fields["service"].queryset = Service.scoped(salon).filter(is_active=True, is_deleted=False)
        for field in self.fields.values():
            if hasattr(field.widget, "attrs"):
                field.widget.attrs.setdefault("class", "input-field")

    class Meta:
        model = CommissionRule
        fields = ["name", "staff", "service", "percent", "fixed_amount_toman", "is_active"]


class SettlementForm(PersianForm):
    amount_toman = TomanAmountField(
        min_value=1,
        error_messages={
            "required": "مبلغ تسویه را وارد کنید.",
            "min_value": "مبلغ باید حداقل ۱ تومان باشد.",
            "invalid": "مبلغ نامعتبر است. فقط عدد تومان با جداکنندهٔ هزارگان وارد کنید.",
        },
    )
    note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "input-field", "rows": 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["amount_toman"].label = "مبلغ تسویه"
        self.fields["note"].label = "توضیحات"
