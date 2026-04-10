from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0003_alter_followup_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='notificationpreference',
            name='notify_all_calls',
            field=models.BooleanField(default=False),
        ),
    ]
