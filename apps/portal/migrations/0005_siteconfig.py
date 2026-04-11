from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0004_notificationpreference_notify_all_calls'),
    ]

    operations = [
        migrations.CreateModel(
            name='SiteConfig',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('company_name', models.CharField(default='Future Smart Support', max_length=128)),
                ('product_name', models.CharField(default='VoiceGate AI', max_length=128)),
                ('contact_email', models.EmailField(blank=True)),
                ('gsm', models.CharField(blank=True, max_length=32)),
                ('website', models.CharField(blank=True, max_length=256)),
                ('office_hours', models.CharField(
                    default='Sunday to Thursday, 9:00 AM to 5:00 PM',
                    max_length=256,
                )),
                ('primary_color', models.CharField(default='#1a56db', max_length=16)),
                ('accent_color', models.CharField(default='#7e3af2', max_length=16)),
                ('notify_all_calls', models.BooleanField(
                    default=False,
                    help_text='Send an email notification for every completed call site-wide.',
                )),
                ('follow_up_emails', models.JSONField(
                    blank=True,
                    default=list,
                    help_text='JSON list of email addresses that receive follow-up notifications.',
                )),
            ],
            options={
                'verbose_name': 'Site Configuration',
                'verbose_name_plural': 'Site Configuration',
                'db_table': 'portal_site_config',
            },
        ),
    ]
