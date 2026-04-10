from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("voice_calls", "0008_alter_callevent_options_alter_callrecord_options_and_more"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RemoveConstraint(
                    model_name="conversationturn",
                    name="uq_turn_session_number",
                ),
            ],
        ),
    ]
