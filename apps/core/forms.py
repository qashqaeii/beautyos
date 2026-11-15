"""Shared form utilities — Persian field labels for ModelForms."""

from django import forms

# برچسب‌های مشترک فیلدها در کل پروژه (کلید = نام فیلد در فرم)
PERSIAN_FIELD_LABELS: dict[str, str] = {
    "name": "نام",
    "full_name": "نام کامل",
    "phone": "موبایل",
    "email": "ایمیل",
    "description": "توضیحات",
    "body": "متن",
    "notes": "یادداشت",
    "title": "عنوان",
    "bio": "بیوگرافی",
    "tagline": "شعار کوتاه",
    "address": "آدرس",
    "city": "شهر",
    "category": "دسته‌بندی",
    "duration_minutes": "مدت زمان (دقیقه)",
    "price_toman": "قیمت (تومان)",
    "sort_order": "ترتیب نمایش",
    "is_active": "فعال",
    "is_public": "نمایش در صفحه عمومی",
    "is_bookable": "قابل رزرو",
    "is_deleted": "حذف‌شده",
    "is_accepting_bookings": "پذیرش رزرو آنلاین",
    "image": "تصویر",
    "avatar": "تصویر پروفایل",
    "logo": "لوگو",
    "cover_image": "تصویر کاور",
    "instagram": "اینستاگرام",
    "whatsapp": "واتساپ",
    "public_phone": "تلفن عمومی",
    "customer": "مشتری",
    "staff": "متخصص",
    "service": "خدمت",
    "services": "خدمات",
    "appointment": "نوبت",
    "start_at": "شروع",
    "end_at": "پایان",
    "status": "وضعیت",
    "source": "منبع",
    "birth_date": "تاریخ تولد",
    "is_vip": "مشتری VIP",
    "marketing_consent": "رضایت پیام تبلیغاتی",
    "tags": "برچسب‌ها",
    "color": "رنگ",
    "display_name": "نام نمایشی",
    "membership": "عضویت",
    "weekday": "روز هفته",
    "start_time": "ساعت شروع",
    "end_time": "ساعت پایان",
    "is_closed": "تعطیل",
    "start_date": "تاریخ شروع",
    "end_date": "تاریخ پایان",
    "reason": "دلیل",
    "method": "روش پرداخت",
    "total_amount_toman": "مبلغ کل (تومان)",
    "discount_toman": "تخفیف (تومان)",
    "paid_amount_toman": "مبلغ پرداخت‌شده (تومان)",
    "amount_toman": "مبلغ (تومان)",
    "expense_date": "تاریخ هزینه",
    "category_id": "دسته",
    "percent": "درصد",
    "staff_id": "متخصص",
    "package": "پکیج",
    "session_count": "تعداد جلسات",
    "validity_days": "اعتبار (روز)",
    "quantity": "موجودی",
    "minimum_quantity": "حداقل موجودی",
    "unit": "واحد",
    "points": "امتیاز",
    "priority": "اولویت",
    "time_note": "زمان ترجیحی",
    "retention_days_30": "پیگیری ۳۰ روز",
    "retention_days_60": "پیگیری ۶۰ روز",
    "retention_days_90": "پیگیری ۹۰ روز",
    "booking_lead_time_minutes": "حداقل فاصله رزرو (دقیقه)",
    "cancellation_notice_hours": "مهلت لغو (ساعت)",
    "code": "کد تأیید",
    "role": "نقش",
    "percent_commission": "درصد پورسانت",
    "note": "توضیح",
    "is_published": "منتشرشده",
    "fixed_amount_toman": "مبلغ ثابت پورسانت (تومان)",
    "slug": "نامک صفحه عمومی",
    "selected_presets": "خدمات پیشنهادی",
    "business_type": "نوع کسب‌وکار",
    "dashboard_theme": "تم پنل مدیریت",
    "public_theme": "قالب صفحه عمومی",
}


class PersianModelForm(forms.ModelForm):
    """ModelForm with Persian labels for known fields and optional Meta.labels merge."""

    extra_persian_labels: dict[str, str] = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.core.widgets import apply_jalali_date_widgets

        apply_jalali_date_widgets(self)
        meta_labels = getattr(self.Meta, "labels", None) or {}
        for name, field in self.fields.items():
            if name in meta_labels:
                field.label = meta_labels[name]
            elif name in self.extra_persian_labels:
                field.label = self.extra_persian_labels[name]
            elif name in PERSIAN_FIELD_LABELS:
                field.label = PERSIAN_FIELD_LABELS[name]


class PersianForm(forms.Form):
    """Plain Form with the same label mapping."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.core.widgets import apply_jalali_date_widgets

        apply_jalali_date_widgets(self)
        for name, field in self.fields.items():
            if name in PERSIAN_FIELD_LABELS and (not field.label or str(field.label).replace(" ", "").isascii()):
                field.label = PERSIAN_FIELD_LABELS[name]
