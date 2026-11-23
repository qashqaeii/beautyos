"""Public SEO metadata and safely structured JSON-LD sources."""
from django.templatetags.static import static
from django.urls import reverse

BRAND = "BeautyOS"
DEFAULT_DESCRIPTION = "بیوتی‌اواس؛ مدیریت نوبت، مشتریان، متخصصان و امور مالی سالن‌های زیبایی زنانه با صفحه اختصاصی و امکان رزرو آنلاین."


def absolute(request, url):
    return request.build_absolute_uri(url)


def brand_schema(request):
    return {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": BRAND,
        "url": absolute(request, reverse("website:home")),
        "logo": absolute(request, static("images/logos/beautyos-logo-3d.webp")),
    }


def meta(request, title, description=DEFAULT_DESCRIPTION, *, canonical=None,
         schema=None, image=None, kind="website", robots="index,follow"):
    desc = (description or DEFAULT_DESCRIPTION).strip()[:320]
    return {
        "seo_title": title, "seo_description": desc,
        "seo_canonical": absolute(request, canonical or request.path),
        "seo_robots": robots, "seo_kind": kind,
        "seo_image": absolute(request, image) if image and image.startswith("/") else image,
        "seo_schema": schema,
    }


def blog_schema(request, post):
    value = {
        "@context": "https://schema.org", "@type": "BlogPosting",
        "headline": post.title, "description": post.summary or post.title,
        "datePublished": post.published_at.isoformat() if post.published_at else "",
        "dateModified": post.updated_at.isoformat(),
        "mainEntityOfPage": absolute(request, reverse("website:blog_post", kwargs={"slug": post.slug})),
        "author": {"@type": "Organization", "name": BRAND},
        "publisher": {"@type": "Organization", "name": BRAND},
    }
    if post.cover_image:
        value["image"] = absolute(request, post.cover_image.url)
    return value


def salon_schema(request, salon, services):
    value = {
        "@context": "https://schema.org", "@type": "BeautySalon",
        "@id": absolute(request, salon.get_public_url()) + "#business",
        "name": salon.name, "url": absolute(request, salon.get_public_url()),
        "description": salon.description or salon.tagline or salon.name,
        "address": {
            "@type": "PostalAddress", "streetAddress": salon.address,
            "addressLocality": salon.city, "addressCountry": "IR",
        },
    }
    if salon.public_phone:
        value["telephone"] = salon.public_phone
    if salon.logo:
        value["logo"] = absolute(request, salon.logo.url)
    if salon.cover_image:
        value["image"] = absolute(request, salon.cover_image.url)
    value["hasOfferCatalog"] = {
        "@type": "OfferCatalog", "name": "خدمات سالن",
        "itemListElement": [
            {"@type": "OfferCatalog", "name": service.name} for service in services[:20]
        ],
    }
    return value
