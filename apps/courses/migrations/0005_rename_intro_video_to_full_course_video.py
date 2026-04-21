from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0004_course_intro_video'),
    ]

    operations = [
        migrations.RenameField(
            model_name='course',
            old_name='intro_video',
            new_name='full_course_video',
        ),
    ]
