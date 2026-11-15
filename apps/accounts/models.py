from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.accounts.managers import UserManager
from apps.core.models import TimeStampedModel
from apps.core.utils.phone import display_iran_mobile


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    phone = models.CharField(max_length=16, unique=True, db_index=True)
    full_name = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    class Meta:
        verbose_name = "کاربر"
        verbose_name_plural = "کاربران"

    def __str__(self):
        return self.full_name or display_iran_mobile(self.phone)

    @property
    def display_phone(self):
        return display_iran_mobile(self.phone)


class OTPChallenge(TimeStampedModel):
    class Purpose(models.TextChoices):
        LOGIN = "login", "ورود"
        REGISTER = "register", "ثبت‌نام"
        BOOKING_VERIFY = "booking_verify", "تأیید رزرو"

    phone = models.CharField(max_length=16, db_index=True)
    purpose = models.CharField(max_length=32, choices=Purpose.choices)
    code_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField(db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)
    request_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["phone", "purpose", "-created_at"]),
        ]

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_consumed(self):
        return self.consumed_at is not None
