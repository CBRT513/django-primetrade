# Generated manually - Rename tenant from Liberty Steel to PrimeTrade

from django.db import migrations


def rename_tenant_to_primetrade(apps, schema_editor):
    """
    Rename the tenant from Liberty Steel to PrimeTrade.
    """
    Tenant = apps.get_model('bol_system', 'Tenant')

    # Update the existing LIBERTY tenant to PRT/PrimeTrade
    Tenant.objects.filter(code='LIBERTY').update(
        code='PRT',
        name='PrimeTrade'
    )


def reverse_migration(apps, schema_editor):
    """
    Reverse: Rename back to Liberty Steel.
    """
    Tenant = apps.get_model('bol_system', 'Tenant')

    Tenant.objects.filter(code='PRT').update(
        code='LIBERTY',
        name='Liberty Steel'
    )


class Migration(migrations.Migration):
    dependencies = [
        ("bol_system", "0031_email_notification_settings"),
    ]

    operations = [
        migrations.RunPython(rename_tenant_to_primetrade, reverse_migration),
    ]
