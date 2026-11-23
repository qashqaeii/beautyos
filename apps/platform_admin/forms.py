from django import forms
from django.utils.text import slugify

from apps.platform_admin.models import SupportMessage, SupportTicket
from apps.website.models import BlogPost


class TicketForm(forms.ModelForm):
    body = forms.CharField(
        label="شرح درخواست", max_length=5000,
        widget=forms.Textarea(attrs={"rows": 5, "placeholder": "موضوع را دقیق توضیح دهید…"}),
    )

    class Meta:
        model = SupportTicket
        fields = ["title", "category"]
        labels = {"title": "عنوان درخواست", "category": "دسته‌بندی"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input-field"

    def clean_title(self):
        return self.cleaned_data["title"].strip()


class MessageForm(forms.ModelForm):
    class Meta:
        model = SupportMessage
        fields = ["body"]
        labels = {"body": "پاسخ"}
        widgets = {"body": forms.Textarea(attrs={"rows": 4, "placeholder": "متن پیام را وارد کنید…"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["body"].widget.attrs["class"] = "input-field"

    def clean_body(self):
        body = self.cleaned_data["body"].strip()
        if not body:
            raise forms.ValidationError("متن پیام نمی‌تواند خالی باشد.")
        return body


class ArticleForm(forms.ModelForm):
    slug = forms.SlugField(label="آدرس مقاله", max_length=220, required=False, allow_unicode=True)

    class Meta:
        model = BlogPost
        fields = ["title", "slug", "category", "summary", "body", "cover_image", "status"]
        labels = {
            "title": "عنوان مقاله", "category": "دسته‌بندی", "summary": "خلاصه",
            "body": "محتوا", "cover_image": "تصویر شاخص", "status": "وضعیت انتشار",
        }
        widgets = {
            "body": forms.Textarea(attrs={"rows": 16}),
            "summary": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_slug(self):
        value = (self.cleaned_data.get("slug") or "").strip()
        if not value:
            value = slugify(self.data.get("title", ""), allow_unicode=True)
        if not value:
            raise forms.ValidationError("آدرس مقاله را وارد کنید.")
        if BlogPost.objects.filter(slug=value).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("این آدرس قبلاً ثبت شده است.")
        return value

    def clean_cover_image(self):
        image = self.cleaned_data.get("cover_image")
        # Existing ImageFieldFile instances have size but no content_type.
        # Requiring a new upload on every text edit would break published posts.
        if image and hasattr(image, "content_type"):
            if image.size > 4 * 1024 * 1024:
                raise forms.ValidationError("حداکثر حجم تصویر ۴ مگابایت است.")
            if image.content_type not in ("image/png", "image/jpeg", "image/webp"):
                raise forms.ValidationError("تصویر باید JPG، PNG یا WebP باشد.")
        return image

    def clean(self):
        data = super().clean()
        if data.get("status") == BlogPost.Status.PUBLISHED:
            if not (data.get("body") or "").strip() or not (data.get("summary") or "").strip():
                raise forms.ValidationError("برای انتشار، متن کامل و خلاصه مقاله ضروری است.")
        return data
