from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bol_system', '0021_bol_care_of_co_release_care_of_co'),
    ]

    operations = [
        migrations.AddField(
            model_name='bol',
            name='pdf_key',
            field=models.CharField(blank=True, help_text='S3 object key for signed URL generation', max_length=500, null=True),
        ),
    ]
