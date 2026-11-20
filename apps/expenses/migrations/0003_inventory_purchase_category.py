from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[("expenses","0002_align_model_state")]
    operations=[migrations.AlterField(model_name="expense",name="category",field=models.CharField(max_length=20,default="other",choices=[
        ("rent","اجاره"),("payroll","حقوق"),("supplies","مواد مصرفی"),("inventory_purchase","خرید موجودی انبار"),
        ("equipment","تجهیزات"),("marketing","تبلیغات"),("utilities","قبوض"),("other","سایر")]))]
