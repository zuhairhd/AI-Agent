"""
Migration: initial KnowledgeDocument table + add original_name and file_size fields.

Since no prior migrations existed for rag_sync, this creates the table from scratch
with all current fields including original_name and file_size.
"""
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='KnowledgeDocument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('file_name', models.CharField(max_length=256)),
                ('original_name', models.CharField(blank=True, default='', max_length=256)),
                ('local_path', models.CharField(max_length=512)),
                ('file_size', models.PositiveBigIntegerField(blank=True, null=True)),
                ('sha256', models.CharField(db_index=True, max_length=64, unique=True)),
                ('openai_file_id', models.CharField(blank=True, db_index=True, max_length=128, null=True)),
                ('vector_store_id', models.CharField(blank=True, max_length=128, null=True)),
                ('sync_status', models.CharField(
                    choices=[
                        ('pending', 'Pending'),
                        ('uploading', 'Uploading'),
                        ('indexed', 'Indexed'),
                        ('failed', 'Failed'),
                    ],
                    db_index=True,
                    default='pending',
                    max_length=16,
                )),
                ('last_synced_at', models.DateTimeField(blank=True, null=True)),
                ('error_message', models.TextField(blank=True, null=True)),
            ],
            options={
                'verbose_name': 'Knowledge Document',
                'verbose_name_plural': 'Knowledge Documents',
                'db_table': 'knowledge_documents',
                'ordering': ['-created_at'],
            },
        ),
    ]
