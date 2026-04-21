from django.contrib import admin

from .models import (
    AssignmentSubmission,
    CartItem,
    Certificate,
    EngagementSnapshot,
    Enrollment,
    LessonProgress,
    MockPaymentTransaction,
    Result,
    Wishlist,
)


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = (
        'student',
        'course',
        'status',
        'payment_status',
        'payment_method',
        'paid_amount',
        'progress_percentage',
        'enrolled_at',
    )
    list_filter = ('status', 'payment_status', 'payment_method')
    search_fields = ('student__username', 'course__title', 'payment_reference')


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ('enrollment', 'lesson', 'is_completed', 'completed_at')
    list_filter = ('is_completed',)


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ('student', 'quiz', 'score_percentage', 'is_passed', 'attempted_at')
    list_filter = ('is_passed',)


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ('certificate_no', 'enrollment', 'issued_at')
    search_fields = ('certificate_no', 'enrollment__student__username', 'enrollment__course__title')


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'created_at')
    search_fields = ('student__username', 'course__title')


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'price_at_added', 'created_at')
    search_fields = ('student__username', 'course__title')


@admin.register(MockPaymentTransaction)
class MockPaymentTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'transaction_id',
        'student',
        'course',
        'payment_method',
        'amount',
        'status',
        'processed_at',
    )
    list_filter = ('status', 'payment_method', 'processed_at')
    search_fields = ('transaction_id', 'student__username', 'course__title')


@admin.register(EngagementSnapshot)
class EngagementSnapshotAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'detected_emotion', 'engagement_score', 'confidence', 'created_at')
    list_filter = ('detected_emotion', 'course')
    search_fields = ('student__username', 'course__title')


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'title', 'plagiarism_score', 'is_flagged', 'created_at')
    list_filter = ('is_flagged', 'course')
    search_fields = ('student__username', 'course__title', 'title')
