from django import forms

from apps.core.forms import PersianModelForm
from apps.salons.models import Salon


class SalonCreateForm(PersianModelForm):
    class Meta:
        model = Salon
        fields = ["name", "public_phone", "city"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input-field", "placeholder": "نام سالن"}),
            "public_phone": forms.TextInput(attrs={"class": "input-field", "inputmode": "tel"}),
            "city": forms.TextInput(attrs={"class": "input-field", "placeholder": "شهر"}),
        }


class SalonProfileForm(PersianModelForm):
    class Meta:
        model = Salon
        fields = ["tagline", "description", "address", "public_theme"]
        widgets = {
            "tagline": forms.TextInput(attrs={"class": "input-field"}),
            "description": forms.Textarea(attrs={"class": "input-field", "rows": 4}),
            "address": forms.Textarea(attrs={"class": "input-field", "rows": 2}),
            "public_theme": forms.Select(attrs={"class": "input-field"}),
        }
