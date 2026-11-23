from __future__ import annotations

from datetime import time

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from django.utils.text import slugify

from apps.core.utils.time_input import parse_hhmm
from apps.salons.business_catalog import presets_for
from apps.salons.models import Salon, SalonMembership, SalonSettings, SalonWorkHours
from apps.salons.themes import BUSINESS_TYPE_DEFAULTS
from apps.services.models import Service
from apps.staff.models import StaffProfile, StaffWorkHours


SESSION_SALON_KEY = "onboarding_salon_id"
SESSION_BUSINESS_TYPE = "onboarding_business_type"
SESSION_SALON_NAME = "onboarding_salon_name"
SESSION_CUSTOM_SERVICES = "onboarding_custom_services"

WIZARD_STEP_LABELS = (
    "اطلاعات اولیه",
    "هویت سالن",
    "خدمات",
    "متخصصان",
    "ساعات کاری",
    "تکمیل",
)

DEFAULT_OPEN_START = time(9, 0)
DEFAULT_OPEN_END = time(21, 0)


def salon_needs_onboarding(salon: Salon | None) -> bool:
    if salon is None:
        return True
    settings = getattr(salon, "settings", None)
    if settings is None:
        return True
    return settings.onboarding_completed_at is None


def apply_business_defaults(salon: Salon, business_type: str) -> None:
    dashboard_key, public_key = BUSINESS_TYPE_DEFAULTS.get(
        business_type,
        BUSINESS_TYPE_DEFAULTS[Salon.BusinessType.COMBINED],
    )
    salon.business_type = business_type
    salon.public_theme = public_key
    salon.save(update_fields=["business_type", "public_theme", "updated_at"])
    settings, _ = SalonSettings.objects.get_or_create(salon=salon)
    settings.dashboard_theme = dashboard_key
    settings.save(update_fields=["dashboard_theme", "updated_at"])


@transaction.atomic
def create_salon_for_owner(user, *, name, slug, public_phone, city, address, tagline, description, business_type, logo=None):
    salon = Salon(
        name=name,
        slug=slugify(slug) if slug else "",
        public_phone=public_phone or "",
        city=city or "",
        address=address or "",
        tagline=tagline or "",
        description=description or "",
        business_type=business_type,
    )
    if logo:
        salon.logo = logo
    salon.save()
    SalonSettings.objects.get_or_create(salon=salon)
    SalonMembership.objects.create(user=user, salon=salon, role=SalonMembership.Role.OWNER)
    apply_business_defaults(salon, business_type)
    return salon


@transaction.atomic
def create_selected_services(salon: Salon, selected_keys: list[str], custom_rows: list[dict]) -> int:
    """selected_keys are indexes as strings matching preset list."""
    presets = presets_for(salon.business_type)
    created = 0
    for key in selected_keys:
        try:
            idx = int(key)
            row = presets[idx]
        except (ValueError, IndexError):
            continue
        if Service.scoped(salon).filter(name=row["name"], is_deleted=False).exists():
            continue
        Service.objects.create(
            salon=salon,
            name=row["name"],
            duration_minutes=row["duration_minutes"],
            price_toman=row["price_toman"],
            is_active=True,
            is_public=True,
        )
        created += 1
    for row in custom_rows:
        name = (row.get("name") or "").strip()
        if not name:
            continue
        if Service.scoped(salon).filter(name=name, is_deleted=False).exists():
            continue
        Service.objects.create(
            salon=salon,
            name=name,
            duration_minutes=int(row.get("duration_minutes") or 30),
            price_toman=int(row.get("price_toman") or 0),
            is_active=True,
            is_public=True,
        )
        created += 1
    return created


def ensure_owner_staff_profile(salon: Salon, user) -> StaffProfile:
    membership = (
        SalonMembership.objects.filter(
            user=user,
            salon=salon,
            is_active=True,
            role=SalonMembership.Role.OWNER,
        )
        .select_related("staff_profile")
        .first()
    )
    if membership is None:
        raise ValidationError("دسترسی مالک سالن یافت نشد.")
    profile = getattr(membership, "staff_profile", None)
    if profile is not None:
        return profile
    display = (getattr(user, "full_name", None) or str(user)).strip()
    return StaffProfile.objects.create(
        salon=salon,
        membership=membership,
        display_name=display,
        title="",
        is_bookable=False,
        is_active=True,
    )


def get_owner_staff_profile(salon: Salon, user) -> StaffProfile | None:
    membership = SalonMembership.objects.filter(
        user=user,
        salon=salon,
        is_active=True,
        role=SalonMembership.Role.OWNER,
    ).first()
    if not membership:
        return None
    return StaffProfile.objects.filter(membership=membership, is_deleted=False).first()


def _default_hours_for_weekday(weekday: int) -> tuple[time, time, bool]:
    if weekday == StaffWorkHours.Weekday.FRI:
        return time(0, 0), time(0, 0), True
    return DEFAULT_OPEN_START, DEFAULT_OPEN_END, False


def _hours_grid(records) -> list[dict]:
    by_day = {row.weekday: row for row in records}
    rows = []
    for choice in StaffWorkHours.Weekday:
        record = by_day.get(choice.value)
        if record:
            rows.append({
                "weekday": choice.value, "label": choice.label,
                "is_closed": record.is_closed,
                "start": record.start_time.strftime("%H:%M") if not record.is_closed else "",
                "end": record.end_time.strftime("%H:%M") if not record.is_closed else "",
            })
        else:
            start, end, closed = _default_hours_for_weekday(choice.value)
            rows.append({
                "weekday": choice.value, "label": choice.label,
                "is_closed": closed,
                "start": "" if closed else start.strftime("%H:%M"),
                "end": "" if closed else end.strftime("%H:%M"),
            })
    return rows


def work_hours_grid(staff: StaffProfile | None) -> list[dict]:
    """Individual specialist's hours, independent of salon opening hours."""
    return _hours_grid(staff.work_hours.all() if staff else [])


def salon_hours_grid(salon: Salon) -> list[dict]:
    """The salon's own weekly schedule; reading never creates an owner specialist."""
    return _hours_grid(SalonWorkHours.objects.filter(salon=salon))


@transaction.atomic
def save_salon_work_hours(salon: Salon, rows: list[dict]) -> None:
    for row in rows:
        SalonWorkHours.objects.update_or_create(
            salon=salon,
            weekday=row["weekday"],
            defaults={
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "is_closed": row["is_closed"],
            },
        )


def apply_default_salon_work_hours(salon: Salon) -> None:
    rows = []
    for choice in SalonWorkHours.Weekday:
        start, end, closed = _default_hours_for_weekday(choice.value)
        rows.append({
            "weekday": choice.value, "is_closed": closed,
            "start_time": start, "end_time": end,
        })
    save_salon_work_hours(salon, rows)


def initialize_owner_specialist_hours(salon: Salon, user) -> None:
    """Only an explicitly bookable owner gets an initial personal schedule."""
    profile = get_owner_staff_profile(salon, user)
    if profile and profile.is_bookable and not profile.work_hours.exists():
        rows = list(SalonWorkHours.objects.filter(salon=salon).values(
            "weekday", "start_time", "end_time", "is_closed"
        ))
        if rows:
            save_staff_work_hours(profile, rows)


def parse_work_hours_post(data) -> tuple[list[dict], list[str]]:
    rows = []
    errors: list[str] = []
    for choice in StaffWorkHours.Weekday:
        prefix = f"wh_{choice.value}"
        is_closed = data.get(f"{prefix}_closed") == "on"
        start_raw = (data.get(f"{prefix}_start") or "").strip()
        end_raw = (data.get(f"{prefix}_end") or "").strip()
        if is_closed:
            rows.append({"weekday": choice.value, "is_closed": True, "start_time": time(0, 0), "end_time": time(0, 0)})
            continue
        try:
            start = parse_hhmm(start_raw) if start_raw else None
            end = parse_hhmm(end_raw) if end_raw else None
        except ValueError:
            errors.append(f"فرمت ساعت روز {choice.label} نامعتبر است.")
            continue
        if start is None:
            errors.append(f"ساعت شروع {choice.label} را وارد کنید.")
            continue
        if end is None:
            errors.append(f"ساعت پایان {choice.label} را وارد کنید.")
            continue
        if end <= start:
            errors.append(f"ساعت پایان {choice.label} باید بعد از شروع باشد.")
            continue
        rows.append({"weekday": choice.value, "is_closed": False, "start_time": start, "end_time": end})
    return rows, errors


@transaction.atomic
def save_staff_work_hours(staff: StaffProfile, rows: list[dict]) -> None:
    for row in rows:
        StaffWorkHours.objects.update_or_create(
            staff=staff,
            weekday=row["weekday"],
            defaults={
                "salon": staff.salon,
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "is_closed": row["is_closed"],
            },
        )


@transaction.atomic
def apply_default_work_hours(staff: StaffProfile) -> None:
    rows = []
    for choice in StaffWorkHours.Weekday:
        start, end, closed = _default_hours_for_weekday(choice.value)
        rows.append(
            {
                "weekday": choice.value,
                "is_closed": closed,
                "start_time": start,
                "end_time": end,
            }
        )
    save_staff_work_hours(staff, rows)


def onboarding_summary(salon: Salon) -> dict:
    from apps.staff.models import StaffProfile

    services = Service.scoped(salon).filter(is_deleted=False, is_active=True).count()
    staff = StaffProfile.scoped(salon).filter(is_deleted=False, is_active=True, is_bookable=True).count()
    hours_count = SalonWorkHours.objects.filter(salon=salon, is_closed=False).count()
    missing = []
    if not (salon.public_phone or "").strip():
        missing.append("شماره تماس عمومی")
    if services == 0:
        missing.append("حداقل یک خدمت")
    if staff == 0:
        missing.append("افزودن متخصص قابل رزرو از بخش کارکنان")
    if hours_count == 0:
        missing.append("ساعات فعالیت سالن")
    if not salon.is_accepting_bookings:
        missing.append("فعال‌سازی آگاهانه رزرو آنلاین از تنظیمات، پس از آماده‌شدن خدمات و تیم")
    return {
        "services": services,
        "staff": staff,
        "hours_configured": hours_count > 0,
        "missing_optional": missing,
    }


@transaction.atomic
def complete_onboarding(salon: Salon) -> bool:
    """Mark onboarding complete; returns False if already completed."""
    settings = SalonSettings.objects.select_for_update().get(salon=salon)
    if settings.onboarding_completed_at is not None:
        return False
    settings.onboarding_completed_at = timezone.now()
    settings.save(update_fields=["onboarding_completed_at", "updated_at"])
    return True
