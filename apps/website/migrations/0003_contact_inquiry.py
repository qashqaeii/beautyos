from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("website", "0002_blogpost_unicode_slug"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ContactInquiry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=100)),
                ("phone", models.CharField(blank=True, max_length=16)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("topic", models.CharField(max_length=20, default="guidance", choices=[
                    ("start", "شروع کار"), ("guidance", "راهنمایی محصول"),
                    ("partnership", "همکاری"), ("other", "سایر موارد"),
                ])),
                ("message", models.TextField(max_length=4000)),
                ("status", models.CharField(max_length=16, db_index=True, default="new", choices=[
                    ("new", "جدید"), ("in_progress", "در حال پیگیری"), ("closed", "بسته‌شده"),
                ])),
                ("ip_digest", models.CharField(blank=True, db_index=True, max_length=64)),
                ("consented_at", models.DateTimeField(blank=True, null=True)),
                ("internal_note", models.TextField(blank=True)),
                ("handled_by", models.ForeignKey(
                    to=settings.AUTH_USER_MODEL, blank=True, null=True,
                    related_name="handled_contact_inquiries",
                    on_delete=django.db.models.deletion.SET_NULL,
                )),
            ],
            options={
                "verbose_name": "پیام تماس سایت",
                "verbose_name_plural": "پیام‌های تماس سایت",
                "ordering": ["-created_at", "-pk"],
                "indexes": [
                    models.Index(fields=["status", "-created_at"], name="web_inquiry_status_idx"),
                ],
            },
        ),
    ]
