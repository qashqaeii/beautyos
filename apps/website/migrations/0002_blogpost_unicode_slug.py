from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("website", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="blogpost",
            name="slug",
            field=models.SlugField(max_length=220, unique=True, allow_unicode=True),
        ),
    ]
