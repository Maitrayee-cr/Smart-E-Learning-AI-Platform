import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.template.defaultfilters import slugify


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Category(TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text='Bootstrap icon class or custom icon name')
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Categories'

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Category.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                counter += 1
                slug = f'{base_slug}-{counter}'
            self.slug = slug
        super().save(*args, **kwargs)


class Course(TimeStampedModel):
    BEGINNER = 'beginner'
    INTERMEDIATE = 'intermediate'
    ADVANCED = 'advanced'
    LEVEL_CHOICES = (
        (BEGINNER, 'Beginner'),
        (INTERMEDIATE, 'Intermediate'),
        (ADVANCED, 'Advanced'),
    )

    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='instructor_courses',
        limit_choices_to={'role': 'instructor'},
    )
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='courses')
    title = models.CharField(max_length=180)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    short_description = models.CharField(max_length=240)
    description = models.TextField()
    thumbnail = models.ImageField(upload_to='course_thumbnails/', blank=True, null=True)
    full_course_video = models.FileField(
        upload_to='course_full_videos/',
        blank=True,
        null=True,
        help_text='Upload full course video (MP4/WEBM/MOV/AVI/MPEG).',
    )
    background_image = models.ImageField(upload_to='course_backgrounds/', blank=True, null=True)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default=BEGINNER)
    duration_hours = models.PositiveIntegerField(default=1)
    language = models.CharField(max_length=50, default='English')
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_featured = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['slug']), models.Index(fields=['title'])]

    def __str__(self) -> str:
        return self.title

    @property
    def is_free(self) -> bool:
        return self.price == 0

    @property
    def average_rating(self) -> float:
        data = self.reviews.filter(is_approved=True).aggregate(avg=models.Avg('rating'))
        return round(data['avg'] or 0, 1)

    @property
    def total_students(self) -> int:
        return self.enrollments.filter(status='active').count()

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Course.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                counter += 1
                slug = f'{base_slug}-{counter}'
            self.slug = slug
        super().save(*args, **kwargs)


class CourseSection(TimeStampedModel):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='sections')
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['order', 'id']
        constraints = [models.UniqueConstraint(fields=['course', 'order'], name='unique_section_order_per_course')]

    def __str__(self) -> str:
        return f'{self.course.title} - {self.title}'


class Lesson(TimeStampedModel):
    section = models.ForeignKey(CourseSection, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=180)
    slug = models.SlugField(max_length=220, blank=True)
    description = models.TextField(blank=True)
    video_url = models.URLField(blank=True)
    video_file = models.FileField(upload_to='lesson_videos/', blank=True, null=True)
    duration_minutes = models.PositiveIntegerField(default=10)
    order = models.PositiveIntegerField(default=1)
    is_preview = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['order', 'id']
        constraints = [models.UniqueConstraint(fields=['section', 'order'], name='unique_lesson_order_per_section')]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            self.slug = f'{base_slug}-{uuid.uuid4().hex[:6]}'
        super().save(*args, **kwargs)


class LessonResource(TimeStampedModel):
    PDF = 'pdf'
    DOC = 'doc'
    ZIP = 'zip'
    LINK = 'link'

    RESOURCE_TYPES = (
        (PDF, 'PDF'),
        (DOC, 'Document'),
        (ZIP, 'Archive'),
        (LINK, 'External Link'),
    )

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='resources')
    title = models.CharField(max_length=180)
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPES, default=PDF)
    file = models.FileField(upload_to='resources/', blank=True, null=True)
    external_url = models.URLField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return self.title


class Quiz(TimeStampedModel):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='quizzes')
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    pass_percentage = models.PositiveSmallIntegerField(default=40)
    time_limit_minutes = models.PositiveSmallIntegerField(default=15)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.lesson.title} - {self.title}'


class Question(TimeStampedModel):
    EASY = 'easy'
    MEDIUM = 'medium'
    HARD = 'hard'
    DIFFICULTY_CHOICES = (
        (EASY, 'Easy'),
        (MEDIUM, 'Medium'),
        (HARD, 'Hard'),
    )

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    order = models.PositiveIntegerField(default=1)
    marks = models.PositiveSmallIntegerField(default=1)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default=MEDIUM)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self) -> str:
        return f'Q{self.order} - {self.quiz.title}'


class Option(TimeStampedModel):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
    text = models.CharField(max_length=250)
    is_correct = models.BooleanField(default=False)

    class Meta:
        ordering = ['id']

    def __str__(self) -> str:
        return self.text


class Review(TimeStampedModel):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='reviews')
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviews',
        limit_choices_to={'role': 'student'},
    )
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    is_approved = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['course', 'student'], name='unique_review_per_student_course')]

    def __str__(self) -> str:
        return f'{self.course.title} - {self.rating} Stars'
