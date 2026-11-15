import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("appointments", "0001_initial"),
        ("customers", "0001_initial"),
        ("services", "0001_initial"),
        ("staff", "0001_initial"),
        ("salons", "0003_invitation_specialist_settings"),
    ]

    operations = [
        migrations.CreateModel(
            name="WaitlistEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("preferred_date", models.DateField(blank=True, null=True)),
                ("time_note", models.CharField(blank=True, max_length=120)),
                ("priority", models.PositiveSmallIntegerField(default=5)),
                ("status", models.CharField(choices=[("open", "فعال"), ("booked", "رزرو شد"), ("closed", "بسته")], default="open", max_length=20)),
                ("appointment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="from_waitlist", to="appointments.appointment")),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="waitlist_entries", to="customers.customer")),
                ("preferred_staff", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="waitlist_entries", to="staff.staffprofile")),
                ("salon", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_set", to="salons.salon")),
                ("service", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="waitlist_entries", to="services.service")),
            ],
        ),
        migrations.AddIndex(model_name="waitlistentry", index=models.Index(fields=["salon", "status", "-priority", "created_at"], name="waitlist_queue_idx")),
    ]
