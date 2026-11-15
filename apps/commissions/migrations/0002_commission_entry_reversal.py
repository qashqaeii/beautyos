import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("commissions", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="commissionentry",
            name="reverses_entry",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reversal_entries",
                to="commissions.commissionentry",
            ),
        ),
        migrations.AlterField(
            model_name="commissionentry",
            name="appointment",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="commission_entry",
                to="appointments.appointment",
            ),
        ),
    ]