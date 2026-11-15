from datetime import date

from django import forms
from django.forms.widgets import Widget
from django.utils import timezone

from apps.core.utils.dates import to_jalali


class JalaliDateWidget(Widget):
    template_name = "widgets/jalali_date.html"

    def __init__(
        self,
        attrs=None,
        *,
        show_calendar_icon: bool = True,
        variant: str = "default",
        max_iso: str | None = None,
    ):
        self.show_calendar_icon = show_calendar_icon
        self.variant = variant
        self.max_iso = max_iso
        default_attrs = {"class": "input-field", "autocomplete": "off"}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)

    def format_value(self, value):
        if value is None:
            return ""
        if isinstance(value, date):
            return value.isoformat()
        return str(value)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        iso = self.format_value(value)
        jalali = ""
        if iso:
            try:
                g = date.fromisoformat(iso)
                jalali = to_jalali(g)
            except ValueError:
                jalali = ""
        max_iso = ""
        if self.max_iso == "today":
            max_iso = timezone.localdate().isoformat()
        elif self.max_iso:
            max_iso = self.max_iso
        context["widget"]["iso_value"] = iso
        context["widget"]["jalali_value"] = jalali
        context["widget"]["show_calendar_icon"] = self.show_calendar_icon
        context["widget"]["variant"] = self.variant
        context["widget"]["birth_picker"] = self.variant == "birth"
        context["widget"]["max_iso"] = max_iso
        return context


class TomanAmountWidget(Widget):
    template_name = "widgets/toman_amount.html"

    def __init__(self, attrs=None):
        default_attrs = {"autocomplete": "off", "inputmode": "numeric"}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)

    def format_value(self, value):
        if value in (None, ""):
            return ""
        from apps.core.utils.money import parse_toman_input

        parsed = parse_toman_input(value)
        if parsed is None:
            return value
        return parsed

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        if value in (None, ""):
            amount_int = 0
        else:
            try:
                amount_int = int(value)
            except (TypeError, ValueError):
                from apps.core.utils.money import parse_toman_input

                parsed = parse_toman_input(value)
                amount_int = parsed if parsed is not None else 0
        context["widget"]["amount_int"] = amount_int
        return context


def apply_jalali_date_widgets(form: forms.BaseForm) -> None:
    for field in form.fields.values():
        if isinstance(field, forms.DateField):
            attrs = dict(getattr(field.widget, "attrs", {}) or {})
            attrs.setdefault("class", "input-field")
            field.widget = JalaliDateWidget(attrs=attrs)
