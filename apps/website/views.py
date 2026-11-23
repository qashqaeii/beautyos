"""BeautyOS public pages, canonical SEO and published content discovery."""
from django.contrib.staticfiles import finders
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.templatetags.static import static
from django.urls import reverse

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
from apps.website.seo import DEFAULT_DESCRIPTION, blog_schema, brand_schema, meta


def _public_ctx(**extra):
    return {
        "feature_groups": FEATURE_GROUPS,
        "start_steps": START_STEPS,
        **extra,
    }


def home(request):
    latest_posts = list(BlogPost.published_qs()[:3])
    hero_path = "images/photos/luna-salon-hero.webp"
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
            **meta(
                request, "مدیریت سالن زیبایی زنانه | BeautyOS", DEFAULT_DESCRIPTION,
                canonical=reverse("website:home"), schema=brand_schema(request),
                image=static(hero_path),
            ),
        ),
    )


def features(request):
    return render(
        request, "website/features.html",
        _public_ctx(
            role_panels=ROLE_PANELS,
            **meta(
                request, "امکانات مدیریت سالن زیبایی | BeautyOS",
                "تقویم شمسی، پرونده مشتری، پذیرش، خدمات، متخصصان، گزارش مالی و رزرو آنلاین سالن زیبایی زنانه.",
                canonical=reverse("website:features"),
            ),
        ),
    )


def blog_index(request):
    posts = BlogPost.published_qs()
    q = (request.GET.get("q") or "").strip()[:80]
    category = (request.GET.get("category") or "").strip()[:80]
    if q:
        posts = posts.filter(
            Q(title__icontains=q) | Q(summary__icontains=q) | Q(body__icontains=q)
        )
    if category:
        posts = posts.filter(category=category)
    categories = (
        BlogPost.published_qs()
        .exclude(category="")
        .values_list("category", flat=True)
        .distinct()
        .order_by("category")
    )
    page_obj = Paginator(posts, 9).get_page(request.GET.get("page"))
    canonical = reverse("website:blog")
    if not q and not category and page_obj.number > 1:
        canonical += f"?page={page_obj.number}"
    return render(
        request, "website/blog_index.html",
        _public_ctx(
            posts=page_obj, page_obj=page_obj, categories=categories,
            active_category=category, q=q, results_count=page_obj.paginator.count,
            **meta(
                request, "مجله مدیریت سالن‌های زیبایی | BeautyOS",
                "راهنماهای کاربردی درباره رزرو آنلاین، مدیریت سالن زیبایی زنانه، امور مالی، تیم و مشتریان.",
                canonical=canonical,
                robots="noindex,follow" if q or category else "index,follow",
            ),
        ),
    )


def blog_post(request, slug):
    post = get_object_or_404(BlogPost.published_qs(), slug=slug)
    related_qs = BlogPost.published_qs().exclude(pk=post.pk)
    if post.category:
        related_qs = related_qs.filter(category=post.category)
    related = list(related_qs[:3])
    return render(
        request, "website/blog_post.html",
        _public_ctx(
            post=post, published_jalali=to_jalali(post.published_at),
            related_posts=related,
            **meta(
                request, f"{post.title} | مجله BeautyOS", post.summary or post.title,
                canonical=reverse("website:blog_post", kwargs={"slug": post.slug}),
                kind="article", schema=blog_schema(request, post),
                image=post.cover_image.url if post.cover_image else None,
            ),
        ),
    )


def contact(request):
    return render(
        request, "website/contact.html",
        _public_ctx(
            **meta(
                request, "تماس با تیم BeautyOS",
                "ارتباط با تیم BeautyOS درباره مدیریت سالن زیبایی زنانه، ثبت‌نام و راهنمایی محصول.",
                canonical=reverse("website:contact"),
            ),
        ),
    )


def faq(request):
    faqs = HOME_FAQ_ITEMS + [
        {
            "q": "چند سالن را می‌توانم با یک شماره مدیریت کنم؟",
            "a": "یک حساب می‌تواند عضو چند سالن باشد و از سوییچر پنل بین آن‌ها جابه‌جا شود.",
        },
        {
            "q": "چه کسی به اطلاعات مشتریان دسترسی دارد؟",
            "a": "فقط کاربران مجاز همان سالن، بر اساس نقش و سطح دسترسی؛ اطلاعات یک سالن برای سالن دیگر قابل مشاهده نیست.",
        },
        {
            "q": "آیا مالک باید متخصص قابل رزرو باشد؟",
            "a": "خیر؛ اضافه‌کردن مالک به فهرست متخصصان اختیاری است و برنامه سالن مستقل از ساعات متخصصان تعریف می‌شود.",
        },
        {
            "q": "آیا رزرو آنلاین بلافاصله بعد از ثبت‌نام فعال است؟",
            "a": "خیر؛ پس از تکمیل خدمات، متخصصان، ساعات کاری و شماره تماس، مالک رزرو آنلاین را از تنظیمات فعال می‌کند.",
        },
    ]
    schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question", "name": item["q"],
                "acceptedAnswer": {"@type": "Answer", "text": item["a"]},
            } for item in faqs
        ],
    }
    return render(
        request, "website/faq.html",
        _public_ctx(
            faqs=faqs,
            **meta(
                request, "سؤالات متداول و راهنمای BeautyOS",
                "پاسخ پرسش‌های پرتکرار درباره راه‌اندازی سالن زنانه، ورود پیامکی، رزرو آنلاین و نقش‌های تیم.",
                canonical=reverse("website:faq"), schema=schema,
            ),
        ),
    )


def privacy(request):
    return render(request, "website/privacy.html", _public_ctx(
        **meta(
            request, "حریم خصوصی | BeautyOS",
            "آشنایی با داده‌های حساب، سالن و مشتریان و نحوه استفاده از آن‌ها در BeautyOS.",
            canonical=reverse("website:privacy"),
        ),
    ))


def terms(request):
    return render(request, "website/terms.html", _public_ctx(
        **meta(
            request, "شرایط استفاده | BeautyOS",
            "قواعد استفاده از سامانه مدیریت سالن زیبایی زنانه، مسئولیت‌های مالک و نقش‌های تیم.",
            canonical=reverse("website:terms"),
        ),
    ))


def robots_txt(request):
    sitemap_url = request.build_absolute_uri(reverse("website:sitemap"))
    return HttpResponse(
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin/\n"
        "Disallow: /control/\n"
        "Disallow: /auth/\n"
        "Disallow: /app/\n"
        "Disallow: /support/\n"
        "Disallow: /settings/\n"
        "Disallow: /s/*/book/\n"
        f"Sitemap: {sitemap_url}\n",
        content_type="text/plain; charset=utf-8",
    )
