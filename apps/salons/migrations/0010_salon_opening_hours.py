from django.db import migrations, models
import django.db.models.deletion


def preserve_existing_owner_hours(apps, schema_editor):
    """Copy prior salon-level settings from owner staff calendars, without changing staff data."""
    using = schema_editor.connection.alias
    Membership = apps.get_model("salons", "SalonMembership")
    Profile = apps.get_model("staff", "StaffProfile")
    StaffHours = apps.get_model("staff", "StaffWorkHours")
    SalonHours = apps.get_model("salons", "SalonWorkHours")
    owners = Membership.objects.using(using).filter(
        role="owner", is_active=True
    ).values_list("salon_id", "id")
    for salon_id, membership_id in owners.iterator():
        profile = Profile.objects.using(using).filter(
            membership_id=membership_id, is_deleted=False
        ).first()
        if profile is None:
            continue
        for hours in StaffHours.objects.using(using).filter(staff_id=profile.pk):
            SalonHours.objects.using(using).get_or_create(
                salon_id=salon_id,
                weekday=hours.weekday,
                defaults={
                    "start_time": hours.start_time,
                    "end_time": hours.end_time,
                    "is_closed": hours.is_closed,
                },
            )


class Migration(migrations.Migration):
    dependencies = [
        ("salons", "0009_onboarding_step"),
        ("staff", "0002_staffprofile_calendar_color"),
    ]

    operations = [
        migrations.CreateModel(
            name="SalonWorkHours",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("weekday", models.PositiveSmallIntegerField(choices=[
                    (0, "شنبه"), (1, "یکشنبه"), (2, "دوشنبه"), (3, "سه‌شنبه"),
                    (4, "چهارشنبه"), (5, "پنجشنبه"), (6, "جمعه"),
                ])),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                ("is_closed", models.BooleanField(default=False)),
                ("salon", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                            related_name="opening_hours", to="salons.salon")),
            ],
            options={
                "verbose_name": "ساعات فعالیت سالن",
                "verbose_name_plural": "ساعات فعالیت سالن",
                "constraints": [
                    models.UniqueConstraint(fields=("salon", "weekday"), name="unique_salon_opening_weekday")
                ],
            },
        ),
        migrations.RunPython(preserve_existing_owner_hours, migrations.RunPython.noop),
    ]
