import django.db.models.deletion
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[("retention","0003_campaigns_cycle")]
    operations=[
        migrations.CreateModel(name="AutomationPolicy",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("created_at",models.DateTimeField(auto_now_add=True,db_index=True)),
            ("updated_at",models.DateTimeField(auto_now=True)),
            ("salon",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="%(app_label)s_%(class)s_set",to="salons.salon")),
            ("reminder_enabled",models.BooleanField(default=False)),
            ("birthday_enabled",models.BooleanField(default=False)),
            ("winback_enabled",models.BooleanField(default=False)),
        ],options={"constraints":[models.UniqueConstraint(fields=["salon"],name="retention_one_automation_policy")]}),
        migrations.CreateModel(name="AutomationMessage",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("created_at",models.DateTimeField(auto_now_add=True,db_index=True)),
            ("updated_at",models.DateTimeField(auto_now=True)),
            ("salon",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="%(app_label)s_%(class)s_set",to="salons.salon")),
            ("customer",models.ForeignKey(to="customers.customer",on_delete=django.db.models.deletion.PROTECT,related_name="automation_messages")),
            ("appointment",models.ForeignKey(to="appointments.appointment",on_delete=django.db.models.deletion.PROTECT,null=True,blank=True,related_name="automation_messages")),
            ("followup",models.ForeignKey(to="retention.followup",on_delete=django.db.models.deletion.PROTECT,null=True,blank=True,related_name="automation_messages")),
            ("kind",models.CharField(max_length=16,choices=[("reminder","یادآوری نوبت"),("birthday","تبریک تولد"),("winback","دعوت به مراجعه")])),
            ("source_key",models.CharField(max_length=100)),
            ("text",models.CharField(max_length=480)),
            ("due_at",models.DateTimeField()),
            ("expires_at",models.DateTimeField()),
            ("status",models.CharField(max_length=12,choices=[("pending","آماده ارسال"),("skipped","صرف‌نظر شده")],default="pending")),
            ("reason",models.CharField(max_length=120,blank=True)),
        ],options={"constraints":[models.UniqueConstraint(fields=["salon","kind","source_key"],name="retention_unique_automation_source")]}),
    ]
