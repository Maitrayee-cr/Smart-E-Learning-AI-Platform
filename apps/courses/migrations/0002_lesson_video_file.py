# Generated manually for adding local video upload support to lessons.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='lesson',
            name='video_file',
            field=models.FileField(blank=True, null=True, upload_to='lesson_videos/'),
        ),
    ]
