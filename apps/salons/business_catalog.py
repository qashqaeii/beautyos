"""Suggested services per business type — user must explicitly select before creation."""

from apps.salons.models import Salon

SERVICE_PRESETS: dict[str, list[dict]] = {
    Salon.BusinessType.BEAUTY_WOMEN: [
        {"name": "کوتاهی و براشینگ", "duration_minutes": 60, "price_toman": 850000},
        {"name": "رنگ و لایت", "duration_minutes": 120, "price_toman": 2500000},
        {"name": "کراتین", "duration_minutes": 150, "price_toman": 3200000},
        {"name": "میکاپ", "duration_minutes": 90, "price_toman": 1800000},
        {"name": "خدمات ناخن", "duration_minutes": 75, "price_toman": 650000},
        {"name": "خدمات مژه", "duration_minutes": 90, "price_toman": 1200000},
        {"name": "خدمات ابرو", "duration_minutes": 45, "price_toman": 450000},
        {"name": "پاک‌سازی پوست", "duration_minutes": 60, "price_toman": 900000},
    ],
    Salon.BusinessType.BARBER_MEN: [
        {"name": "اصلاح مو", "duration_minutes": 45, "price_toman": 400000},
        {"name": "اصلاح ریش", "duration_minutes": 30, "price_toman": 250000},
        {"name": "فید", "duration_minutes": 50, "price_toman": 500000},
        {"name": "گریم داماد", "duration_minutes": 90, "price_toman": 1500000},
        {"name": "خدمات پوست", "duration_minutes": 40, "price_toman": 350000},
        {"name": "رنگ مو", "duration_minutes": 60, "price_toman": 700000},
        {"name": "خدمات VIP", "duration_minutes": 75, "price_toman": 1200000},
    ],
    Salon.BusinessType.COMBINED: [
        {"name": "کوتاهی مو", "duration_minutes": 45, "price_toman": 450000},
        {"name": "اصلاح ریش", "duration_minutes": 30, "price_toman": 250000},
        {"name": "رنگ مو", "duration_minutes": 90, "price_toman": 1200000},
        {"name": "پاک‌سازی پوست", "duration_minutes": 50, "price_toman": 750000},
        {"name": "میکاپ", "duration_minutes": 75, "price_toman": 1400000},
        {"name": "خدمات ناخن", "duration_minutes": 60, "price_toman": 550000},
    ],
}


def presets_for(business_type: str) -> list[dict]:
    return list(SERVICE_PRESETS.get(business_type, SERVICE_PRESETS[Salon.BusinessType.COMBINED]))
