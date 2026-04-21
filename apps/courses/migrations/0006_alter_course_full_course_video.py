from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0005_rename_intro_video_to_full_course_video'),
    ]

    operations = [
        migrations.AlterField(
            model_name='course',
            name='full_course_video',
            field=models.FileField(
                blank=True,
                help_text='Upload full course video (MP4/WEBM/MOV/AVI/MPEG).',
                null=True,
                upload_to='course_full_videos/',
            ),
        ),
    ]
