from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_remove_user_assigned_route_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='demo_latitude',
            field=models.FloatField(
                blank=True,
                help_text='Preset demo location latitude for investor presentations.',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='demo_longitude',
            field=models.FloatField(
                blank=True,
                help_text='Preset demo location longitude for investor presentations.',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='demo_location_label',
            field=models.CharField(
                blank=True,
                help_text='Human-readable label for the demo location, e.g. "Githurai 45".',
                max_length=255,
            ),
        ),
    ]
