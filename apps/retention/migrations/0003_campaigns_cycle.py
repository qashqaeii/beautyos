import django.db.models.deletion
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("retention","0002_initial")]
    operations = [
        migrations.AddField(model_name="followup",name="cycle_key",field=models.CharField(blank=True,default="",max_length=64)),
        migrations.AddConstraint(model_name="followup",constraint=models.UniqueConstraint(fields=("salon","customer","cycle_key"),condition=~models.Q(cycle_key=""),name="retention_unique_followup_cycle")),
        migrations.CreateModel(name="Campaign",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("created_at",models.DateTimeField(auto_now_add=True,db_index=True)),
            ("updated_at",models.DateTimeField(auto_now=True)),
            ("salon",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="%(app_label)s_%(class)s_set",to="salons.salon")),
            ("title",models.CharField(max_length=100)),
            ("segment",models.CharField(max_length=16,choices=[("active","مشتریان فعال"),("at_risk","نیازمند پیگیری"),("inactive","مشتریان غیرفعال"),("new","بدون مراجعه انجام‌شده"),("vip","مشتریان ویژه"),("birthday","تولد این ماه")])),
            ("message",models.CharField(max_length=480)),
            ("status",models.CharField(max_length=16,choices=[("draft","پیش‌نویس"),("prepared","مخاطبان آماده"),("cancelled","لغوشده")],default="draft")),
            ("request_key",models.UUIDField()),
            ("prepared_at",models.DateTimeField(blank=True,null=True)),
        ],options={"constraints":[models.UniqueConstraint(fields=("salon","request_key"),name="retention_campaign_request")]}),
        migrations.CreateModel(name="CampaignRecipient",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("created_at",models.DateTimeField(auto_now_add=True,db_index=True)),
            ("updated_at",models.DateTimeField(auto_now=True)),
            ("salon",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="%(app_label)s_%(class)s_set",to="salons.salon")),
            ("campaign",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="recipients",to="retention.campaign")),
            ("customer",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="campaign_recipients",to="customers.customer")),
            ("message_snapshot",models.CharField(max_length=480)),
        ],options={"constraints":[models.UniqueConstraint(fields=("campaign","customer"),name="retention_campaign_customer")]}),
    ]
