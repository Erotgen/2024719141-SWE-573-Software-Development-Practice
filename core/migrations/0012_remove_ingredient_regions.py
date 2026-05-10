from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_recipe_latitude_recipe_longitude'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='ingredient',
            name='regions',
        ),
    ]
