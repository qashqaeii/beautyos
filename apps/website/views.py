from django.contrib.staticfiles import finders
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from apps.core.utils.dates import to_jalali
from apps.website.features_data import (
    FEATURE_GROUPS,
    HOME_FAQ_ITEMS,
    HOME_LANDING_HIGHLIGHTS,
    HOME_MODULE_SPOTLIGHTS,
    HOME_VALUE_PROPS,
    ROLE_PANELS,
    START_STEPS,
)
from apps.website.models import BlogPost


def _public_ctx(**extra):
    return {
        "feature_groups": FEATURE_GROUPS,
        "start_steps": START_STEPS,
        **extra,
    }


def home(request):
    latest_posts = list(BlogPost.published_qs()[:3])
    hero_path = "images/photos/luna-salon-hero.webp"
    # The approved asset is tracked in Git. Keep a warm salon fallback for
    # incomplete local static directories; never bring back the lavender portrait.
    hero_available = bool(finders.find(hero_path))
    if not hero_available:
        hero_path = "images/photos/Sunlit Salon with Twin Hairstyle Portraits.webp"
    return render(
        request,
        "website/home.html",
        _public_ctx(
            latest_posts=latest_posts,
            hero_image_path=hero_path,
            hero_image_width=1440 if hero_available else 1728,
            hero_image_height=960 if hero_available else 864,
            hero_image_is_fallback=not hero_available,
            landing_highlights=HOME_LANDING_HIGHLIGHTS,
            home_value_props=HOME_VALUE_PROPS,
            module_spotlights=HOME_MODULE_SPOTLIGHTS,
            home_faqs=HOME_FAQ_ITEMS,
        ),
    )


def features(request):
    return render(
        request,
        "website/features.html",
        _public_ctx(role_panels=ROLE_PANELS),
    )


def blog_index(request):
    posts = BlogPost.published_qs()
    category = (request.GET.get("category") or "").strip()
    if category:
        posts = posts.filter(category=category)
    categories = (
        BlogPost.published_qs()
        .exclude(category="")
        .values_list("category", flat=True)
        .distinct()
        .order_by("category")
    )
    return render(
        request,
        "website/blog_index.html",
        _public_ctx(posts=posts, categories=categories, active_category=category),
    )


def blog_post(request, slug):
    post = get_object_or_404(BlogPost.published_qs(), slug=slug)
    related_qs = BlogPost.published_qs().exclude(pk=post.pk)
    if post.category:
        related_qs = related_qs.filter(category=post.category)
    related = list(related_qs[:3])
    return render(
        request,
        "website/blog_post.html",
        _public_ctx(
            post=post,
            published_jalali=to_jalali(post.published_at),
            related_posts=related,
        ),
    )


def contact(request):
    return render(request, "website/contact.html", _public_ctx())


def faq(request):
    faqs = [
        {
            "q": "BeautyOS برای چه سالن‌هایی مناسب است؟",
            "a": (
                "سالن‌های زیبایی، آرایشگاه مردانه و هر کسب‌وکاری که نوبت‌دهی، "
                "مدیریت مشتری و تیم دارد — از پذیرش روزانه تا گزارش مالی."
            ),
        },
        {
            "q": "ثبت‌نام سالن چقدر طول می‌کشد؟",
            "a": (
                "با شماره موبایل مالک، تأیید کد پیامکی و وارد کردن نام، "
                "سالن و پنل مدیریت در همان جلسه ساخته می‌شود؛ سپس خدمات و تیم را اضافه کنید."
            ),
        },
        {
            "q": "مشتریان چطور نوبت می‌گیرند؟",
            "a": (
                "از صفحه عمومی اختصاصی سالن شما در آدرس s/نام-سالن/ "
                "می‌توانند خدمت، متخصص و زمان را انتخاب و نوبت ثبت کنند؛ "
                "نوبت در تقویم پنل و میز پذیرش نمایش داده می‌شود."
            ),
        },
        {
            "q": "ورود با رمز عبور است؟",
            "a": (
                "خیر. ورود مالک، منشی و متخصص با کد یک‌بار مصرف پیامکی "
                "روی شماره موبایل ثبت‌شده انجام می‌شود؛ نیازی به به‌خاطر سپردن رمز نیست."
            ),
        },
        {
            "q": "چند سالن می‌توانم داشته باشم؟",
            "a": (
                "با یک شماره موبایل می‌توانید مالک یا عضو چند سالن باشید "
                "و از سوییچر داخل پنل بین آن‌ها جابه‌جا شوید."
            ),
        },
        {
            "q": "چه کسی به اطلاعات مشتریان دسترسی دارد؟",
            "a": (
                "فقط اعضای مجاز همان سالن و مطابق نقش (مدیر، منشی، متخصص) "
                "به پرونده مشتری و نوبت‌ها دسترسی دارند؛ جزئیات در صفحه حریم خصوصی آمده است."
            ),
        },
    ]
    return render(request, "website/faq.html", _public_ctx(faqs=faqs))


def privacy(request):
    return render(request, "website/privacy.html", _public_ctx())


def terms(request):
    return render(request, "website/terms.html", _public_ctx())