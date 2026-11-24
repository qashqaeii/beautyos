from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("packages", "0002_align_model_state"),
    ]

    operations = [
        migrations.AddField(
            model_name="packagesessionuse",
            name="reversed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
