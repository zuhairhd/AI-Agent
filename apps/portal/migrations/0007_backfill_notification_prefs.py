"""
Data migration: ensure every existing User has a NotificationPreference row.

New users get one auto-created via the post_save signal added in this release.
This migration covers everyone who registered before that signal existed.
"""

from django.db import migrations


def backfill_notification_prefs(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    NotificationPreference = apps.get_model('portal', 'NotificationPreference')

    existing_user_ids = set(
        NotificationPreference.objects.values_list('user_id', flat=True)
    )

    to_create = [
        NotificationPreference(user=user)
        for user in User.objects.exclude(pk__in=existing_user_ids)
    ]

    if to_create:
        NotificationPreference.objects.bulk_create(to_create, ignore_conflicts=True)

    created_count = len(to_create)
    if created_count:
        print(f"\n  [0007] Created NotificationPreference for {created_count} existing user(s).")
    else:
        print("\n  [0007] All users already have a NotificationPreference; nothing to do.")


def noop_reverse(apps, schema_editor):
    # We do not delete prefs on reverse — they may have been edited.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0006_alter_siteconfig_id'),
        ('auth', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(backfill_notification_prefs, noop_reverse),
    ]
