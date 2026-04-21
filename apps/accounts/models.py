from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class User(AbstractUser, TimeStampedModel):
    STUDENT = 'student'
    INSTRUCTOR = 'instructor'
    ADMIN = 'admin'

    ROLE_CHOICES = (
        (STUDENT, 'Student'),
        (INSTRUCTOR, 'Instructor'),
        (ADMIN, 'Admin'),
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=STUDENT, db_index=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    bio = models.TextField(blank=True)
    is_email_verified = models.BooleanField(default=False)

    class Meta:
        ordering = ['-date_joined']

    def __str__(self) -> str:
        return f'{self.get_full_name() or self.username} ({self.role})'

    @property
    def is_student(self) -> bool:
        return self.role == self.STUDENT

    @property
    def is_instructor(self) -> bool:
        return self.role == self.INSTRUCTOR

    @property
    def is_platform_admin(self) -> bool:
        return self.role == self.ADMIN or self.is_superuser


class StudentProfile(TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    enrollment_no = models.CharField(max_length=40, blank=True)
    university = models.CharField(max_length=120, blank=True)
    semester = models.PositiveSmallIntegerField(default=1)
    city = models.CharField(max_length=80, blank=True)
    learning_interests = models.TextField(blank=True, help_text='Comma separated interests such as Python, AI, design')

    class Meta:
        ordering = ['user__first_name', 'user__last_name']

    def __str__(self) -> str:
        return f'Student Profile - {self.user.username}'


class InstructorProfile(TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='instructor_profile')
    headline = models.CharField(max_length=180, blank=True)
    qualification = models.CharField(max_length=120, blank=True)
    experience_years = models.PositiveSmallIntegerField(default=0)
    expertise = models.CharField(max_length=200, blank=True)
    approved = models.BooleanField(default=True)

    class Meta:
        ordering = ['user__first_name', 'user__last_name']

    def __str__(self) -> str:
        return f'Instructor Profile - {self.user.username}'


@receiver(post_save, sender=User)
def create_role_profile(sender, instance, created, **kwargs):
    if not created:
        return

    if instance.role == User.STUDENT:
        StudentProfile.objects.get_or_create(user=instance)
    elif instance.role == User.INSTRUCTOR:
        InstructorProfile.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
def save_role_profile(sender, instance, **kwargs):
    if instance.role == User.STUDENT and hasattr(instance, 'student_profile'):
        instance.student_profile.save()
    elif instance.role == User.INSTRUCTOR and hasattr(instance, 'instructor_profile'):
        instance.instructor_profile.save()
