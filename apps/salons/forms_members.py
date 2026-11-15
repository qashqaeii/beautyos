from django import forms

from apps.core.forms import PersianForm
from apps.salons.models import SalonMembership


class InviteMemberForm(PersianForm):
    phone = forms.CharField(
        label="شماره موبایل",
        widget=forms.TextInput(attrs={"class": "input-field", "inputmode": "tel"}),
    )
    role = forms.ChoiceField(
        label="نقش",
        choices=SalonMembership.Role.choices,
        widget=forms.Select(attrs={"class": "input-field"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = [
            c for c in SalonMembership.Role.choices if c[0] != SalonMembership.Role.OWNER
        ]
