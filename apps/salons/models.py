import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from apps.core.models import TimeStampedModel


def salon_cover_path(instance, filename):
    return f"salons/{instance.id}/cover/{filename}"


def salon_logo_path(instance, filename):
    return f"salons/{instance.id}/logo/{filename}"


class Salon(TimeStampedModel):
    class BusinessType(models.TextChoices):
        BEAUTY_WOMEN = "beauty_women", "سالن زیبایی زنانه"
        BARBER_MEN = "barber_men", "آرایشگاه مردانه"
        COMBINED = "combined", "سالن ترکیبی / استودیو"

    class PublicTheme(models.TextChoices):
        ELEGANT_BEAUTY = "elegant_beauty", "ظریف — Lavender (عمومی)"
        MODERN_BARBER = "modern_barber", "مردانه — Gentleman (عمومی)"
        MINIMAL_STUDIO = "minimal_studio", "خنثی — Neutral (عمومی)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, db_index=True)
    tagline = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    public_phone = models.CharField(max_length=16, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=80, blank=True)
    is_active = models.BooleanField(default=True)
    is_accepting_bookings = models.BooleanField(default=True)
    business_type = models.CharField(
        max_length=32,
        choices=BusinessType.choices,
        default=BusinessType.COMBINED,
    )
    public_theme = models.CharField(
        max_length=32,
        choices=PublicTheme.choices,
        default=PublicTheme.MINIMAL_STUDIO,
    )
    logo = models.ImageField(upload_to=salon_logo_path, blank=True, null=True)
    cover_image = models.ImageField(upload_to=salon_cover_path, blank=True, null=True)
    instagram = models.CharField(max_length=120, blank=True)
    whatsapp = models.CharField(max_length=32, blank=True)

    class Meta:
        verbose_name = "سالن"
        verbose_name_plural = "سالن‌ها"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name, allow_unicode=False) or slugify(self.name, allow_unicode=True)
            if not base:
                base = f"salon-{str(self.id)[:8]}"
            candidate = base
            n = 1
            while Salon.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base}-{n}"
                n += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    def get_public_url(self):
        return reverse("salons_public:landing", kwargs={"slug": self.slug})


class SalonSettings(TimeStampedModel):
    class DashboardTheme(models.TextChoices):
        ROSE_ATELIER = "rose_atelier", "آتلیه یاسی (Lavender)"
        MODERN_GENTLEMAN = "modern_gentleman", "مردانه مدرن"
        SIGNATURE_NEUTRAL = "signature_neutral", "خنثی کلاسیک"

    salon = models.OneToOneField(Salon, on_delete=models.CASCADE, related_name="settings")
    dashboard_theme = models.CharField(
        max_length=32,
        choices=DashboardTheme.choices,
        default=DashboardTheme.SIGNATURE_NEUTRAL,
    )
    onboarding_completed_at = models.DateTimeField(null=True, blank=True)
    onboarding_deferred_at = models.DateTimeField(null=True, blank=True)
    specialist_can_view_commission = models.BooleanField(default=False)
    retention_days_30 = models.PositiveSmallIntegerField(default=30)
    retention_days_60 = models.PositiveSmallIntegerField(default=60)
    retention_days_90 = models.PositiveSmallIntegerField(default=90)
    booking_lead_time_minutes = models.PositiveIntegerField(default=60)
    cancellation_notice_hours = models.PositiveIntegerField(default=2)
    sms_transactional_enabled = models.BooleanField(default=True)
    sms_marketing_enabled = models.BooleanField(default=False)
    currency_code = models.CharField(max_length=3, default="IRR")
    timezone = models.CharField(max_length=64, default="Asia/Tehran")

    class Meta:
        verbose_name = "تنظیمات سالن"
        verbose_name_plural = "تنظیمات سالن‌ها"


class SalonMembership(TimeStampedModel):
    class Role(models.TextChoices):
        OWNER = "owner", "مالک"
        MANAGER = "manager", "مدیر"
        RECEPTIONIST = "receptionist", "منشی"
        SPECIALIST = "specialist", "متخصص"

    ROLE_RANK = {
        Role.SPECIALIST: 10,
        Role.RECEPTIONIST: 20,
        Role.MANAGER: 30,
        Role.OWNER: 40,
    }

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="salon_memberships",
    )
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.OWNER)
    is_active = models.BooleanField(default=True)
    title = models.CharField(max_length=80, blank=True)
    can_manage_staff = models.BooleanField(
        default=False,
        help_text="منشی: مدیریت متخصص‌ها (بدون پورسانت و اعضا)",
    )

    class Meta:
        unique_together = [("user", "salon")]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["salon", "role"]),
        ]

    def __str__(self):
        return f"{self.user} @ {self.salon} ({self.role})"

    @property
    def role_rank(self):
        return self.ROLE_RANK.get(self.role, 0)

    @classmethod
    def role_rank_for(cls, role: str) -> int:
        return cls.ROLE_RANK.get(role, 0)


class SalonInvitation(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار"
        ACCEPTED = "accepted", "پذیرفته"
        CANCELLED = "cancelled", "لغو شده"

    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="invitations")
    phone = models.CharField(max_length=16, db_index=True)
    invitee_first_name = models.CharField(max_length=60, blank=True)
    invitee_last_name = models.CharField(max_length=60, blank=True)
    invitee_specialty = models.CharField(max_length=80, blank=True)
    invitee_service = models.ForeignKey(
        "services.Service", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="specialist_invitations",
    )
    role = models.CharField(max_length=20, choices=SalonMembership.Role.choices, default=SalonMembership.Role.RECEPTIONIST)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="salon_invites_sent")
    token = models.CharField(max_length=64, unique=True, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    expires_at = models.DateTimeField()

    class Meta:
        indexes = [models.Index(fields=["salon", "status"])]

    def __str__(self):
        return f"{self.phone} → {self.salon} ({self.role})"


class SalonScopedModelMixin(models.Model):
    """Alias mixin name used in docs; delegates to core tenant."""

    class Meta:
        abstract = True
