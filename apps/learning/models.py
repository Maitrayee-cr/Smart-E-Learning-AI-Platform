import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.courses.models import Course, Lesson, Quiz


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Enrollment(TimeStampedModel):
    ACTIVE = 'active'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'
    STATUS_CHOICES = (
        (ACTIVE, 'Active'),
        (COMPLETED, 'Completed'),
        (CANCELLED, 'Cancelled'),
    )
    PAYMENT_FREE = 'free'
    PAYMENT_PENDING = 'pending'
    PAYMENT_PAID = 'paid'
    PAYMENT_FAILED = 'failed'
    PAYMENT_STATUS_CHOICES = (
        (PAYMENT_FREE, 'Free'),
        (PAYMENT_PENDING, 'Pending'),
        (PAYMENT_PAID, 'Paid'),
        (PAYMENT_FAILED, 'Failed'),
    )
    PAYMENT_UPI = 'upi'
    PAYMENT_CARD = 'card'
    PAYMENT_NET_BANKING = 'net_banking'
    PAYMENT_WALLET = 'wallet'
    PAYMENT_METHOD_CHOICES = (
        (PAYMENT_UPI, 'UPI'),
        (PAYMENT_CARD, 'Credit / Debit Card'),
        (PAYMENT_NET_BANKING, 'Net Banking'),
        (PAYMENT_WALLET, 'Wallet'),
    )

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='enrollments',
        limit_choices_to={'role': 'student'},
    )
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=ACTIVE)
    progress_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, blank=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default=PAYMENT_FREE)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_reference = models.CharField(max_length=60, blank=True)
    payment_at = models.DateTimeField(blank=True, null=True)
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-enrolled_at']
        constraints = [models.UniqueConstraint(fields=['student', 'course'], name='unique_student_course_enrollment')]

    def __str__(self) -> str:
        return f'{self.student.username} -> {self.course.title}'


class LessonProgress(TimeStampedModel):
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='lesson_progress')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='progress_entries')
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['lesson__section__order', 'lesson__order']
        constraints = [models.UniqueConstraint(fields=['enrollment', 'lesson'], name='unique_enrollment_lesson_progress')]

    def __str__(self) -> str:
        return f'{self.enrollment.student.username} - {self.lesson.title}'


class Result(TimeStampedModel):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='quiz_results',
        limit_choices_to={'role': 'student'},
    )
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='results')
    total_questions = models.PositiveIntegerField(default=0)
    correct_answers = models.PositiveIntegerField(default=0)
    score_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    is_passed = models.BooleanField(default=False)
    attempted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-attempted_at']

    def __str__(self) -> str:
        return f'{self.student.username} - {self.quiz.title} ({self.score_percentage}%)'


class Certificate(TimeStampedModel):
    enrollment = models.OneToOneField(Enrollment, on_delete=models.CASCADE, related_name='certificate')
    certificate_no = models.CharField(max_length=30, unique=True, blank=True)
    issued_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-issued_at']

    def __str__(self) -> str:
        return f'Certificate {self.certificate_no}'

    def save(self, *args, **kwargs):
        if not self.certificate_no:
            year = timezone.now().year
            suffix = uuid.uuid4().hex[:8].upper()
            self.certificate_no = f'SEL-{year}-{suffix}'
        super().save(*args, **kwargs)


class Wishlist(TimeStampedModel):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wishlist_items',
        limit_choices_to={'role': 'student'},
    )
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='wishlisted_by')

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['student', 'course'], name='unique_wishlist_student_course')]

    def __str__(self) -> str:
        return f'{self.student.username} likes {self.course.title}'


class CartItem(TimeStampedModel):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cart_items',
        limit_choices_to={'role': 'student'},
    )
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='cart_items')
    price_at_added = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['student', 'course'], name='unique_cart_student_course')]

    def __str__(self) -> str:
        return f'{self.student.username} cart -> {self.course.title}'


class MockPaymentTransaction(TimeStampedModel):
    STATUS_PENDING = 'pending'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pending'),
        (STATUS_SUCCESS, 'Success'),
        (STATUS_FAILED, 'Failed'),
    )

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='mock_payments',
        limit_choices_to={'role': 'student'},
    )
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, related_name='mock_payments')
    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mock_payments',
    )
    transaction_id = models.CharField(max_length=50, unique=True, blank=True)
    payment_method = models.CharField(max_length=20, choices=Enrollment.PAYMENT_METHOD_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    gateway_name = models.CharField(max_length=50, default='SmartLMS MockPay')
    response_message = models.CharField(max_length=255, blank=True)
    request_payload = models.JSONField(default=dict, blank=True)
    processed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-processed_at']

    def __str__(self) -> str:
        return f'{self.transaction_id} ({self.get_status_display()})'

    def save(self, *args, **kwargs):
        if not self.transaction_id:
            self.transaction_id = f'TXN-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:10].upper()}'
        super().save(*args, **kwargs)


class EngagementSnapshot(TimeStampedModel):
    ATTENTIVE = 'attentive'
    CONFUSED = 'confused'
    BORED = 'bored'
    HAPPY = 'happy'
    EMOTION_CHOICES = (
        (ATTENTIVE, 'Attentive'),
        (CONFUSED, 'Confused'),
        (BORED, 'Bored'),
        (HAPPY, 'Happy'),
    )

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='engagement_snapshots',
        limit_choices_to={'role': 'student'},
    )
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='engagement_snapshots')
    image = models.ImageField(upload_to='engagement_snapshots/', blank=True, null=True)
    detected_emotion = models.CharField(max_length=20, choices=EMOTION_CHOICES, default=ATTENTIVE)
    engagement_score = models.PositiveSmallIntegerField(default=50)
    confidence = models.PositiveSmallIntegerField(default=70)
    analysis = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.student.username} - {self.course.title} - {self.detected_emotion}'


class AssignmentSubmission(TimeStampedModel):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assignment_submissions',
        limit_choices_to={'role': 'student'},
    )
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='assignment_submissions')
    title = models.CharField(max_length=180)
    content = models.TextField()
    plagiarism_score = models.PositiveSmallIntegerField(default=0)
    matched_submission = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='matched_by_submissions',
    )
    similarity_report = models.TextField(blank=True)
    is_flagged = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.student.username} - {self.title}'
