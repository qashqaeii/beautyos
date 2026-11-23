from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from apps.core.models import TimeStampedModel


class BlogPost(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "پیش‌نویس"
        PUBLISHED = "published", "منتشرشده"

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, db_index=True, allow_unicode=True)
    summary = models.CharField(max_length=320, blank=True)
    body = models.TextField()
    category = models.CharField(max_length=80, blank=True, db_index=True)
    cover_image = models.ImageField(upload_to="blog/covers/", blank=True, null=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = "مقاله بلاگ"
        verbose_name_plural = "مقالات بلاگ"
        ordering = ["-published_at", "-created_at"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title, allow_unicode=True) or "post"
            candidate = base
            n = 1
            while BlogPost.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base}-{n}"
                n += 1
            self.slug = candidate
        if self.status == self.Status.PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    @classmethod
    def published_qs(cls):
        return cls.objects.filter(
            status=cls.Status.PUBLISHED,
            published_at__isnull=False,
            published_at__lte=timezone.now(),
        )

class ContactInquiry(TimeStampedModel):
    """Public contact message; raw visitor IPs are not stored."""

    class Topic(models.TextChoices):
        START = "start", "شروع کار"
        GUIDANCE = "guidance", "راهنمایی محصول"
        PARTNERSHIP = "partnership", "همکاری"
        OTHER = "other", "سایر موارد"

    class Status(models.TextChoices):
        NEW = "new", "جدید"
        IN_PROGRESS = "in_progress", "در حال پیگیری"
        CLOSED = "closed", "بسته‌شده"

    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=16, blank=True)
    email = models.EmailField(blank=True)
    topic = models.CharField(max_length=20, choices=Topic.choices, default=Topic.GUIDANCE)
    message = models.TextField(max_length=4000)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NEW, db_index=True)
    ip_digest = models.CharField(max_length=64, blank=True, db_index=True)
    consented_at = models.DateTimeField(null=True, blank=True)
    internal_note = models.TextField(blank=True)
    handled_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="handled_contact_inquiries",
    )

    class Meta:
        verbose_name = "پیام تماس سایت"
        verbose_name_plural = "پیام‌های تماس سایت"
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(fields=["status", "-created_at"], name="web_inquiry_status_idx"),
        ]

    def __str__(self):
        return f"{self.name}: {self.get_topic_display()}"
