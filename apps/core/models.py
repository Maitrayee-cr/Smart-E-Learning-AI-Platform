from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ContactMessage(TimeStampedModel):
    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    subject = models.CharField(max_length=180)
    message = models.TextField()
    is_resolved = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.name} - {self.subject}'


class FAQ(TimeStampedModel):
    question = models.CharField(max_length=250)
    answer = models.TextField()
    order = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self) -> str:
        return self.question


class Testimonial(TimeStampedModel):
    name = models.CharField(max_length=120)
    designation = models.CharField(max_length=120, blank=True)
    content = models.TextField()
    rating = models.PositiveSmallIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    is_featured = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.name} - {self.rating} stars'
