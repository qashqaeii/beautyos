from django import forms

from apps.core.utils.phone import normalize_iran_mobile
from apps.website.models import ContactInquiry


class ContactInquiryForm(forms.ModelForm):
    consent = forms.BooleanField(
        label="با پردازش اطلاعات تماس من برای پاسخ طبق حریم خصوصی موافقم."
    )
    website_url = forms.CharField(
        required=False, widget=forms.HiddenInput(attrs={"autocomplete": "off"}), label=""
    )

    class Meta:
        model = ContactInquiry
        fields = ["name", "phone", "email", "topic", "message"]
        labels = {
            "name": "نام و نام خانوادگی", "phone": "موبایل (اختیاری)", "email": "ایمیل (اختیاری)",
            "topic": "موضوع پیام", "message": "پیام شما",
        }
        widgets = {
            "name": forms.TextInput(attrs={"autocomplete": "name", "placeholder": "نام خود را وارد کنید"}),
            "phone": forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "tel", "dir": "ltr", "placeholder": "۰۹۱۲…"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email", "dir": "ltr", "placeholder": "email@example.com"}),
            "message": forms.Textarea(attrs={"rows": 5, "placeholder": "چطور می‌توانیم کمک کنیم؟"}),
        }

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if len(name) < 2:
            raise forms.ValidationError("نام را کامل وارد کنید.")
        return name

    def clean_phone(self):
        raw = (self.cleaned_data.get("phone") or "").strip()
        if not raw:
            return ""
        try:
            return normalize_iran_mobile(raw)
        except ValueError as exc:
            raise forms.ValidationError(str(exc)) from exc

    def clean_message(self):
        value = self.cleaned_data["message"].strip()
        if len(value) < 12:
            raise forms.ValidationError("پیام را حداقل در ۱۲ کاراکتر توضیح دهید.")
        return value

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("phone") and not cleaned.get("email"):
            raise forms.ValidationError("برای دریافت پاسخ، موبایل یا ایمیل خود را وارد کنید.")
        return cleaned
