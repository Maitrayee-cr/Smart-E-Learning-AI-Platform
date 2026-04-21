from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0003_course_background_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='intro_video',
            field=models.FileField(blank=True, null=True, upload_to='course_intro_videos/'),
        ),
    ]
