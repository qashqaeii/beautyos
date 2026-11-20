import django.db.models.deletion
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("loyalty","0005_referrals_vouchers"),("packages","0002_align_model_state")]
    operations = [
        migrations.CreateModel(name="MembershipCycle",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("created_at",models.DateTimeField(auto_now_add=True,db_index=True)),
            ("updated_at",models.DateTimeField(auto_now=True)),
            ("salon",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="%(app_label)s_%(class)s_set",to="salons.salon")),
            ("purchase",models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,related_name="membership_cycle",to="packages.customerpackage")),
            ("renewed_from",models.OneToOneField(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name="renewal",to="loyalty.membershipcycle")),
            ("request_key",models.UUIDField()),
        ],options={"constraints":[models.UniqueConstraint(fields=("salon","request_key"),name="loyalty_membership_request")]}),
    ]
