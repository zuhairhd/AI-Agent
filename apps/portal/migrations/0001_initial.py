import uuid
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('voice_calls', '0006_callsession_portal_fields'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Alert',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('alert_type',  models.CharField(max_length=32, db_index=True, choices=[('low_confidence','Low AI Confidence'),('no_answer','No Answer Found'),('human_requested','Human Agent Requested'),('dropped_call','Call Dropped'),('repeated_failure','Repeated Failed Interaction'),('unresolved','Call Unresolved')])),
                ('severity',    models.CharField(max_length=8,  default='medium', db_index=True, choices=[('high','High'),('medium','Medium'),('low','Low')])),
                ('status',      models.CharField(max_length=16, default='open',   db_index=True, choices=[('open','Open'),('acknowledged','Acknowledged'),('resolved','Resolved'),('dismissed','Dismissed')])),
                ('title',       models.CharField(max_length=256)),
                ('description', models.TextField(blank=True)),
                ('resolved_at', models.DateTimeField(null=True, blank=True)),
                ('send_email',    models.BooleanField(default=False)),
                ('email_sent',    models.BooleanField(default=False)),
                ('email_sent_at', models.DateTimeField(null=True, blank=True)),
                ('session', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='alerts', to='voice_calls.callsession')),
                ('assigned_to', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_alerts', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'portal_alerts', 'ordering': ['-created_at'], 'verbose_name': 'Alert', 'verbose_name_plural': 'Alerts'},
        ),
        migrations.AddIndex(
            model_name='alert',
            index=models.Index(fields=['status', 'created_at'], name='idx_alert_status_created'),
        ),
        migrations.AddIndex(
            model_name='alert',
            index=models.Index(fields=['alert_type', 'status'], name='idx_alert_type_status'),
        ),
        migrations.CreateModel(
            name='FollowUp',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('status',   models.CharField(max_length=16, default='pending',  db_index=True, choices=[('pending','Pending'),('in_progress','In Progress'),('completed','Completed'),('cancelled','Cancelled')])),
                ('priority', models.CharField(max_length=8,  default='medium',   db_index=True, choices=[('high','High'),('medium','Medium'),('low','Low')])),
                ('notes',        models.TextField(blank=True)),
                ('due_date',     models.DateTimeField(null=True, blank=True)),
                ('completed_at', models.DateTimeField(null=True, blank=True)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='followups', to='voice_calls.callsession')),
                ('alert',   models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='followups', to='portal.alert')),
                ('assigned_to', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_followups', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'portal_followups', 'ordering': ['-created_at'], 'verbose_name': 'Follow-up', 'verbose_name_plural': 'Follow-ups'},
        ),
        migrations.AddIndex(
            model_name='followup',
            index=models.Index(fields=['status', 'priority'], name='idx_followup_status_priority'),
        ),
        migrations.CreateModel(
            name='NotificationPreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email_enabled',     models.BooleanField(default=True)),
                ('notify_on',         models.JSONField(default=list)),
                ('notify_email',      models.EmailField(blank=True)),
                ('sms_enabled',       models.BooleanField(default=False)),
                ('sms_number',        models.CharField(max_length=32, blank=True)),
                ('whatsapp_enabled',  models.BooleanField(default=False)),
                ('whatsapp_number',   models.CharField(max_length=32, blank=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='notification_pref', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'portal_notification_preferences', 'verbose_name': 'Notification Preference', 'verbose_name_plural': 'Notification Preferences'},
        ),
    ]
