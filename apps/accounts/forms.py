from django import forms

from apps.core.utils.phone import normalize_iran_mobile


class PhoneForm(forms.Form):
    phone = forms.CharField(
        label="شماره موبایل",
        max_length=20,
        widget=forms.TextInput(
            attrs={
                "class": "input-field input-field--tel",
                "type": "tel",
                "dir": "ltr",
                "placeholder": "۰۹۱۲۳۴۵۶۷۸۹",
                "inputmode": "tel",
                "autocomplete": "tel",
            }
        ),
    )

    def clean_phone(self):
        try:
            return normalize_iran_mobile(self.cleaned_data["phone"])
        except ValueError as exc:
            raise forms.ValidationError(str(exc)) from exc


class OTPVerifyForm(forms.Form):
    code = forms.CharField(
        label="کد تأیید",
        max_length=6,
        min_length=6,
        widget=forms.TextInput(
            attrs={
                "class": "input-field text-center text-2xl tracking-[0.35em]",
                "placeholder": "۱۲۳۴۵۶",
                "inputmode": "numeric",
                "autocomplete": "one-time-code",
                "maxlength": "6",
            }
        ),
    )

    def clean_code(self):
        code = self.cleaned_data["code"].translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
        if not code.isdigit():
            raise forms.ValidationError("کد باید ۶ رقم باشد.")
        return code


class RegisterProfileForm(forms.Form):
    full_name = forms.CharField(
        label="نام و نام خانوادگی",
        max_length=120,
        widget=forms.TextInput(attrs={"class": "input-field", "autocomplete": "name"}),
    )
