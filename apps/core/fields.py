from django import forms
from django.core.exceptions import ValidationError

from apps.core.utils.money import parse_toman_input
from apps.core.widgets import TomanAmountWidget


class TomanAmountField(forms.IntegerField):
    widget = TomanAmountWidget

    default_error_messages = {
        "invalid": "مبلغ نامعتبر است. فقط عدد تومان با جداکنندهٔ هزارگان وارد کنید.",
    }

    def to_python(self, value):
        if value in self.empty_values:
            return None
        if isinstance(value, bool):
            raise ValidationError(self.error_messages["invalid"], code="invalid")
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            trimmed = value.strip()
            if trimmed.isdigit():
                return int(trimmed)
            parsed = parse_toman_input(trimmed)
            if parsed is None:
                raise ValidationError(self.error_messages["invalid"], code="invalid")
            return parsed
        return super().to_python(value)
