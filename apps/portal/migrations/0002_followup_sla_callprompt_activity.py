import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # SLA fields on FollowUp
        migrations.AddField(
            model_name='followup',
            name='sla_deadline',
            field=models.DateTimeField(null=True, blank=True, db_index=True),
        ),
        migrations.AddField(
            model_name='followup',
            name='sla_breached',
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AddField(
            model_name='followup',
            name='reminded_at',
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='followup',
            name='source',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('rag_failure',   'RAG Failure'),
                    ('human_request', 'Human Request'),
                    ('unresolved',    'Unresolved Call'),
                    ('manual',        'Manual'),
                    ('sla_breach',    'SLA Breach'),
                ],
                default='manual',
                db_index=True,
            ),
        ),
        migrations.AlterField(
            model_name='followup',
            name='priority',
            field=models.CharField(
                max_length=8,
                choices=[
                    ('urgent', 'Urgent'),
                    ('high',   'High'),
                    ('medium', 'Medium'),
                    ('low',    'Low'),
                ],
                default='medium',
                db_index=True,
            ),
        ),
        migrations.AlterField(
            model_name='followup',
            name='status',
            field=models.CharField(
                max_length=16,
                choices=[
                    ('pending',     'Pending'),
                    ('in_progress', 'In Progress'),
                    ('assigned',    'Assigned'),
                    ('completed',   'Completed'),
                    ('cancelled',   'Cancelled'),
                    ('resolved',    'Resolved'),
                    ('closed',      'Closed'),
                ],
                default='pending',
                db_index=True,
            ),
        ),
        # CallPrompt model
        migrations.CreateModel(
            name='CallPrompt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stem',         models.CharField(max_length=64, unique=True, db_index=True)),
                ('language',     models.CharField(max_length=8, default='en')),
                ('text',         models.TextField()),
                ('audio_path',   models.CharField(max_length=512, blank=True)),
                ('audio_exists', models.BooleanField(default=False)),
                ('version',      models.PositiveIntegerField(default=1)),
                ('enabled',      models.BooleanField(default=True)),
                ('updated_at',   models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'portal_call_prompts', 'ordering': ['stem'], 'verbose_name': 'Call Prompt', 'verbose_name_plural': 'Call Prompts'},
        ),
        # FollowUpActivity model
        migrations.CreateModel(
            name='FollowUpActivity',
            fields=[
                ('id',          models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('action',      models.CharField(max_length=64, choices=[('assigned','Assigned'),('reassigned','Reassigned'),('claimed','Claimed'),('status_changed','Status Changed'),('note_added','Note Added'),('escalated','Escalated'),('resolved','Resolved'),('closed','Closed')])),
                ('description', models.TextField(blank=True)),
                ('created_at',  models.DateTimeField(auto_now_add=True)),
                ('followup',    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='activities', to='portal.followup')),
                ('user',        models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, related_name='followup_activities', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'portal_followup_activities', 'ordering': ['-created_at'], 'verbose_name': 'Follow-up Activity', 'verbose_name_plural': 'Follow-up Activities'},
        ),
    ]
