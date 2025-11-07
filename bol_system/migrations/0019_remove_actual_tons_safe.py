# Safe migration to remove actual_tons if it exists
from django.db import migrations


def remove_actual_tons_if_exists(apps, schema_editor):
    """Remove actual_tons column if it exists"""
    with schema_editor.connection.cursor() as cursor:
        # Check if column exists
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='bol_system_releaseload'
            AND column_name='actual_tons'
        """)

        if cursor.fetchone():
            # Column exists, drop it
            cursor.execute('ALTER TABLE bol_system_releaseload DROP COLUMN IF EXISTS actual_tons')
            print("✓ Dropped actual_tons column")
        else:
            print("✓ actual_tons column already removed")


class Migration(migrations.Migration):

    dependencies = [
        ('bol_system', '0018_remove_actual_tons_field'),
    ]

    operations = [
        migrations.RunPython(remove_actual_tons_if_exists, migrations.RunPython.noop),
    ]
