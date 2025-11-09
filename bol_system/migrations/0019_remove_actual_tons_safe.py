# Safe migration to remove actual_tons if it exists
from django.db import migrations


def remove_actual_tons_if_exists(apps, schema_editor):
    """Remove actual_tons column if it exists"""
    with schema_editor.connection.cursor() as cursor:
        # Check if column exists (SQLite-compatible using PRAGMA)
        if schema_editor.connection.vendor == 'sqlite':
            cursor.execute("PRAGMA table_info(bol_system_releaseload)")
            columns = [row[1] for row in cursor.fetchall()]
            column_exists = 'actual_tons' in columns
        else:
            # PostgreSQL/other databases
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='bol_system_releaseload'
                AND column_name='actual_tons'
            """)
            column_exists = cursor.fetchone() is not None

        if column_exists:
            # Column exists, drop it
            cursor.execute('ALTER TABLE bol_system_releaseload DROP COLUMN actual_tons')
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
