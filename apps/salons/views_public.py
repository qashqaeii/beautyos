from django.shortcuts import get_object_or_404, render

from apps.portfolio.models import PortfolioItem
from apps.salons.models import Salon
from apps.salons.themes import css_variables_inline_public
from apps.services.models import Service
from apps.staff.models import StaffProfile


_THEME_TEMPLATES = {
    Salon.PublicTheme.ELEGANT_BEAUTY: "public/themes/elegant_beauty.html",
    Salon.PublicTheme.MODERN_BARBER: "public/themes/modern_barber.html",
    Salon.PublicTheme.MINIMAL_STUDIO: "public/themes/minimal_studio.html",
}


def public_landing(request, slug):
    salon = get_object_or_404(Salon, slug=slug, is_active=True)
    services = Service.scoped(salon).filter(is_active=True, is_public=True, is_deleted=False)
    staff = StaffProfile.scoped(salon).filter(is_active=True, is_bookable=True, is_deleted=False)
    portfolio = PortfolioItem.scoped(salon).filter(is_published=True, is_deleted=False)[:12]
    template = _THEME_TEMPLATES.get(salon.public_theme, _THEME_TEMPLATES[Salon.PublicTheme.MINIMAL_STUDIO])
    context = {
        "salon": salon,
        "services": services,
        "staff_list": staff,
        "portfolio": portfolio,
        "public_theme_style": css_variables_inline_public(),
    }
    return render(request, template, context)
