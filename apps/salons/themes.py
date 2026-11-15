"""Dashboard & public theme tokens — runtime CSS variables (no CSS rebuild)."""

from __future__ import annotations

from apps.salons.models import Salon


class DashboardTheme:
    """Active UI uses LUNA_SIGNATURE (Editorial Rose) only; legacy keys remain for stored settings."""

    LUNA_SIGNATURE = "luna_signature"
    ROSE_ATELIER = "rose_atelier"
    MODERN_GENTLEMAN = "modern_gentleman"
    SIGNATURE_NEUTRAL = "signature_neutral"

    CHOICES = (
        (LUNA_SIGNATURE, "Editorial Rose"),
        (ROSE_ATELIER, "آتلیه یاسی (Legacy)"),
        (MODERN_GENTLEMAN, "مردانه مدرن (Legacy)"),
        (SIGNATURE_NEUTRAL, "خنثی کلاسیک (Legacy)"),
    )


GLOBAL_DASHBOARD_THEME = DashboardTheme.LUNA_SIGNATURE

LUNA_SIGNATURE_TOKENS: dict[str, str] = {
    "--color-primary": "#9D726E",
    "--color-primary-hover": "#8A635F",
    "--color-primary-foreground": "#FFFFFF",
    "--color-text-primary": "#51443F",
    "--color-text-heading": "#51443F",
    "--color-text-secondary": "#857771",
    "--color-text-on-primary": "#FFFFFF",
    "--color-text-muted": "#9A8B85",
    "--color-background": "#F5F0EC",
    "--color-surface": "#FAF7F4",
    "--color-surface-elevated": "#FFFDFC",
    "--color-surface-muted": "#FAF7F4",
    "--color-surface-lavender": "#E9D8D2",
    "--color-surface-sage": "#D8C9C1",
    "--color-success-background": "#E8F0EA",
    "--color-success-text": "#4D6B56",
    "--color-border": "#E5DCD6",
    "--color-border-strong": "#D5CAC3",
    "--color-divider": "#E5DCD6",
    "--color-focus": "#9D726E",
    "--color-sidebar": "#F5F0EC",
    "--color-sidebar-text": "#51443F",
    "--color-sidebar-muted": "#857771",
    "--color-sidebar-hover": "#E9D8D2",
    "--color-sidebar-active": "#E9D8D2",
    "--color-accent": "#B58D89",
    "--color-accent-soft": "#E9D8D2",
    "--color-sage": "#769B82",
    "--color-sage-soft": "#E5EDE7",
    "--color-blush": "#E9D8D2",
}


DASHBOARD_THEME_TOKENS: dict[str, dict[str, str]] = {
    DashboardTheme.LUNA_SIGNATURE: dict(LUNA_SIGNATURE_TOKENS),
    DashboardTheme.ROSE_ATELIER: dict(LUNA_SIGNATURE_TOKENS),
    DashboardTheme.MODERN_GENTLEMAN: {
        "--color-primary": "#51443F",
        "--color-primary-hover": "#3D322E",
        "--color-accent": "#857771",
        "--color-accent-soft": "#D8C9C1",
        "--color-background": "#F5F0EC",
        "--color-surface": "#FFFDFC",
        "--color-surface-muted": "#FAF7F4",
        "--color-text-primary": "#51443F",
        "--color-text-secondary": "#857771",
        "--color-text-muted": "#9A8B85",
        "--color-border": "#E5DCD6",
        "--color-border-strong": "#D5CAC3",
        "--color-sidebar": "#51443F",
        "--color-sidebar-hover": "#6B5A54",
        "--color-sidebar-active": "#857771",
    },
    DashboardTheme.SIGNATURE_NEUTRAL: {
        "--color-primary": "#9D726E",
        "--color-primary-hover": "#8A635F",
        "--color-accent": "#B58D89",
        "--color-accent-soft": "#E9D8D2",
        "--color-background": "#F5F0EC",
        "--color-surface": "#FFFDFC",
        "--color-surface-muted": "#FAF7F4",
        "--color-text-primary": "#51443F",
        "--color-text-secondary": "#857771",
        "--color-text-muted": "#9A8B85",
        "--color-border": "#E5DCD6",
        "--color-border-strong": "#D5CAC3",
        "--color-sidebar": "#51443F",
        "--color-sidebar-hover": "#6B5A54",
        "--color-sidebar-active": "#857771",
    },
}

SHARED_STATUS_TOKENS = {
    "--color-success": "#769B82",
    "--color-success-background": "#E8F0EA",
    "--color-success-text": "#4D6B56",
    "--color-warning": "#C79A57",
    "--color-danger": "#B96E6C",
}

BUSINESS_TYPE_DEFAULTS = {
    Salon.BusinessType.BEAUTY_WOMEN: (DashboardTheme.ROSE_ATELIER, Salon.PublicTheme.ELEGANT_BEAUTY),
    Salon.BusinessType.BARBER_MEN: (DashboardTheme.MODERN_GENTLEMAN, Salon.PublicTheme.MODERN_BARBER),
    Salon.BusinessType.COMBINED: (DashboardTheme.SIGNATURE_NEUTRAL, Salon.PublicTheme.MINIMAL_STUDIO),
}


def resolve_global_dashboard_theme(salon=None) -> str:
    """Single active dashboard/public workspace theme for all tenants."""
    return GLOBAL_DASHBOARD_THEME


def resolve_salon_dashboard_theme(salon) -> str:
    """Preserved API — always returns global theme; SalonSettings.dashboard_theme is not used for render."""
    return resolve_global_dashboard_theme(salon)


def css_variables_for_dashboard(theme_key: str | None = None) -> dict[str, str]:
    del theme_key  # reserved for legacy previews; runtime always uses global theme
    base = dict(DASHBOARD_THEME_TOKENS[resolve_global_dashboard_theme()])
    base.update(SHARED_STATUS_TOKENS)
    return base


def css_variables_inline(theme_key: str | None = None) -> str:
    pairs = css_variables_for_dashboard(theme_key)
    return "; ".join(f"{k}: {v}" for k, v in pairs.items())


def css_variables_for_public() -> dict[str, str]:
    return css_variables_for_dashboard(GLOBAL_DASHBOARD_THEME)


def css_variables_inline_public() -> str:
    return css_variables_inline(GLOBAL_DASHBOARD_THEME)


def css_variables_for_public_elegant() -> dict[str, str]:
    """Backward-compatible alias."""
    return css_variables_for_public()


def css_variables_inline_public_elegant() -> str:
    """Backward-compatible alias."""
    return css_variables_inline_public()