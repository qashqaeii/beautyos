from datetime import time

from django import forms

from apps.core.utils.time_input import parse_hhmm


class Time24TextInput(forms.TextInput):
    def __init__(self, attrs=None):
        default_attrs = {
            "class": "input-field input-field--time24",
            "dir": "ltr",
            "inputmode": "numeric",
            "autocomplete": "off",
            "maxlength": "5",
            "spellcheck": "false",
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)

    def format_value(self, value):
        if isinstance(value, time):
            return value.strftime("%H:%M")
        return super().format_value(value)


class HHmmTimeField(forms.Field):
    widget = Time24TextInput

    def to_python(self, value):
        if value in (None, ""):
            return None
        if isinstance(value, time):
            return value
        return parse_hhmm(str(value))
