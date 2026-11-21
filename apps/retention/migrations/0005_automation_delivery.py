import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("retention", "0004_automation_queue")]
    operations = [
        migrations.AddField(model_name="campaign", name="scheduled_at", field=models.DateTimeField(null=True, blank=True)),
        migrations.AlterField(model_name="campaign", name="status", field=models.CharField(max_length=16, default="draft", choices=[("draft", "پیش‌نویس"), ("prepared", "مخاطبان آماده"), ("scheduled", "زمان‌بندی‌شده"), ("cancelled", "لغوشده")])),
        migrations.AddField(model_name="automationpolicy", name="confirmation_enabled", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="automationpolicy", name="cancellation_enabled", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="automationpolicy", name="daily_marketing_cap", field=models.PositiveSmallIntegerField(default=30)),
        migrations.AddField(model_name="automationmessage", name="campaign_recipient", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="automation_messages", to="retention.campaignrecipient")),
        migrations.AddField(model_name="automationmessage", name="attempted_at", field=models.DateTimeField(null=True, blank=True)),
        migrations.AddField(model_name="automationmessage", name="last_checked_at", field=models.DateTimeField(null=True, blank=True)),
        migrations.AddField(model_name="automationmessage", name="provider_message_id", field=models.CharField(blank=True, max_length=64)),
        migrations.AlterField(model_name="automationmessage", name="kind", field=models.CharField(max_length=16, choices=[("reminder", "یادآوری نوبت"), ("birthday", "تبریک تولد"), ("winback", "دعوت به مراجعه"), ("confirmation", "تأیید نوبت"), ("cancellation", "لغو نوبت"), ("campaign", "کمپین")])),
        migrations.AlterField(model_name="automationmessage", name="status", field=models.CharField(max_length=12, default="pending", choices=[("pending", "آماده ارسال"), ("claimed", "در حال ارسال"), ("accepted", "پذیرفته‌شده"), ("delivered", "تحویل‌شده"), ("failed", "ناموفق"), ("unknown", "نامشخص"), ("skipped", "صرف‌نظر شده")])),
        migrations.AddIndex(model_name="automationmessage", index=models.Index(fields=["status", "due_at"], name="retention_send_due_idx")),
    ]
