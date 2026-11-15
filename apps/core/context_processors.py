from django.conf import settings

from apps.core.utils.dates import today_jalali_label


def global_context(request):
    return {
        "BEAUTYOS_PRODUCT_NAME": "BeautyOS",
        "BEAUTYOS_SITE_LOGO": "images/logos/Logo.webp",
        "BEAUTYOS_DEBUG": settings.DEBUG,
        "BEAUTYOS_ASSET_VERSION": settings.BEAUTYOS_ASSET_VERSION,
        "today_jalali": today_jalali_label(),
    }
