from django.db import migrations, models
from django.utils import timezone


def backfill_onboarding_completed(apps, schema_editor):
    SalonSettings = apps.get_model("salons", "SalonSettings")
    now = timezone.now()
    for row in SalonSettings.objects.filter(onboarding_completed_at__isnull=True):
        row.onboarding_completed_at = row.created_at or now
        row.save(update_fields=["onboarding_completed_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("salons", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="salon",
            name="business_type",
            field=models.CharField(
                choices=[
                    ("beauty_women", "سالن زیبایی زنانه"),
                    ("barber_men", "آرایشگاه مردانه"),
                    ("combined", "سالن ترکیبی / استودیو"),
                ],
                default="combined",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="salonsettings",
            name="dashboard_theme",
            field=models.CharField(
                choices=[
                    ("rose_atelier", "Rose Atelier"),
                    ("modern_gentleman", "Modern Gentleman"),
                    ("signature_neutral", "Signature Neutral"),
                ],
                default="signature_neutral",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="salonsettings",
            name="onboarding_completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_onboarding_completed, migrations.RunPython.noop),
    ]
