import json
import random
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.decorators import student_required
from apps.courses.forms import ReviewForm
from apps.courses.models import Course, Lesson, LessonResource, Quiz, Review

from .ai_features import (
    analyze_engagement_snapshot,
    analyze_plagiarism_submission,
    build_learning_path,
    build_video_summary,
    predict_student_performance,
)
from .forms import AssignmentSubmissionForm, EngagementSnapshotForm, PaymentMethodForm
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
from .services import (
    build_student_ai_insights,
    evaluate_quiz_submission,
    get_personalized_recommendations,
    issue_certificate_if_eligible,
    recalculate_course_progress,
)


def _redirect_to_next_or_default(request, next_url, default_name, **kwargs):
    if next_url and url_has_allowed_host_and_scheme(next_url, {request.get_host()}, require_https=request.is_secure()):
        return redirect(next_url)
    return redirect(default_name, **kwargs)


def _build_mock_request_payload(payment_method, cleaned_data):
    if payment_method == Enrollment.PAYMENT_UPI:
        return {'upi_id': cleaned_data.get('upi_id', '')}
    if payment_method == Enrollment.PAYMENT_CARD:
        card_number = (cleaned_data.get('card_number') or '').replace(' ', '')
        masked_card = f'**** **** **** {card_number[-4:]}' if len(card_number) >= 4 else '****'
        return {
            'card_holder_name': cleaned_data.get('card_holder_name', ''),
            'card_number': masked_card,
            'card_expiry': cleaned_data.get('card_expiry', ''),
        }
    if payment_method == Enrollment.PAYMENT_NET_BANKING:
        return {
            'bank_name': cleaned_data.get('bank_name', ''),
            'netbanking_user_id': cleaned_data.get('netbanking_user_id', ''),
        }
    if payment_method == Enrollment.PAYMENT_WALLET:
        return {'wallet': 'SmartLMS Wallet'}
    return {}


def _simulate_mock_payment_result(cleaned_data):
    preference = cleaned_data.get('mock_result') or PaymentMethodForm.MOCK_SUCCESS
    if preference == PaymentMethodForm.MOCK_SUCCESS:
        return MockPaymentTransaction.STATUS_SUCCESS, 'Payment completed successfully in mock gateway.'
    if preference == PaymentMethodForm.MOCK_FAILED:
        return MockPaymentTransaction.STATUS_FAILED, 'Mock gateway declined this transaction.'
    if preference == PaymentMethodForm.MOCK_PENDING:
        return MockPaymentTransaction.STATUS_PENDING, 'Payment is pending confirmation in mock gateway.'
    if preference == PaymentMethodForm.MOCK_RANDOM:
        is_success = random.choice([True, False])
        return (
            MockPaymentTransaction.STATUS_SUCCESS if is_success else MockPaymentTransaction.STATUS_FAILED,
            'Random mock result generated.',
        )
    return MockPaymentTransaction.STATUS_SUCCESS, 'Payment completed successfully in mock gateway.'


def _create_mock_payment_transaction(student, course, amount, payment_method, cleaned_data):
    status, message = _simulate_mock_payment_result(cleaned_data)
    return MockPaymentTransaction.objects.create(
        student=student,
        course=course,
        amount=amount,
        payment_method=payment_method,
        status=status,
        response_message=message,
        request_payload=_build_mock_request_payload(payment_method, cleaned_data),
        processed_at=timezone.now(),
    )


@student_required
def student_dashboard(request):
    enrollments = Enrollment.objects.filter(student=request.user).select_related('course')
    latest_enrollments = enrollments.order_by('-enrolled_at')[:5]
    ai_insights = build_student_ai_insights(request.user)
    ai_recommendations = get_personalized_recommendations(request.user, limit=3)
    performance_prediction = predict_student_performance(request.user)
    focus_enrollment = latest_enrollments[0] if latest_enrollments else None
    optimized_learning_path = build_learning_path(focus_enrollment) if focus_enrollment else None
    wishlist_count = Wishlist.objects.filter(student=request.user).count()
    cart_count = CartItem.objects.filter(student=request.user).count()
    certificates_count = Certificate.objects.filter(enrollment__student=request.user).count()
    payment_success_count = MockPaymentTransaction.objects.filter(
        student=request.user,
        status=MockPaymentTransaction.STATUS_SUCCESS,
    ).count()

    context = {
        'stats': {
            'enrollments': enrollments.count(),
            'active_courses': enrollments.filter(status='active').count(),
            'completed_courses': enrollments.filter(status='completed').count(),
            'avg_progress': round(sum(float(e.progress_percentage) for e in enrollments) / (enrollments.count() or 1), 2),
            'wishlist_count': wishlist_count,
            'cart_count': cart_count,
            'certificates_count': certificates_count,
            'payment_success_count': payment_success_count,
        },
        'latest_enrollments': latest_enrollments,
        'ai_insights': ai_insights,
        'ai_recommendations': ai_recommendations,
        'performance_prediction': performance_prediction,
        'optimized_learning_path': optimized_learning_path,
        'chart_data_json': json.dumps(
            {
                'labels': [enrollment.course.title for enrollment in latest_enrollments],
                'values': [float(enrollment.progress_percentage) for enrollment in latest_enrollments],
            }
        ),
    }
    return render(request, 'student/dashboard.html', context)


@student_required
def my_learning(request):
    enrollments = Enrollment.objects.filter(student=request.user).select_related('course').order_by('-enrolled_at')
    paginator = Paginator(enrollments, 9)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'student/my_learning.html', {'page_obj': page_obj})


@student_required
def wishlist_page(request):
    wishlist_items = Wishlist.objects.filter(student=request.user).select_related('course', 'course__instructor')
    cart_course_ids = set(CartItem.objects.filter(student=request.user).values_list('course_id', flat=True))
    enrolled_course_ids = set(Enrollment.objects.filter(student=request.user).values_list('course_id', flat=True))
    paginator = Paginator(wishlist_items, 9)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(
        request,
        'student/wishlist.html',
        {
            'page_obj': page_obj,
            'cart_course_ids': cart_course_ids,
            'enrolled_course_ids': enrolled_course_ids,
        },
    )


def _render_cart_page(request, payment_form=None):
    cart_items = CartItem.objects.filter(student=request.user).select_related('course', 'course__instructor')
    total_amount = sum((item.course.price for item in cart_items), Decimal('0.00'))
    has_paid_items = any(item.course.price > 0 for item in cart_items)
    return render(
        request,
        'student/cart.html',
        {
            'cart_items': cart_items,
            'total_amount': total_amount,
            'has_paid_items': has_paid_items,
            'payment_form': payment_form or PaymentMethodForm(),
        },
    )


@student_required
def cart_page(request):
    return _render_cart_page(request)


@student_required
def add_to_cart(request, slug):
    course = get_object_or_404(Course, slug=slug, is_published=True)

    if Enrollment.objects.filter(student=request.user, course=course).exists():
        messages.info(request, f'You are already enrolled in {course.title}.')
        return redirect('learning:enrolled_course_detail', slug=course.slug)

    item, created = CartItem.objects.get_or_create(
        student=request.user,
        course=course,
        defaults={'price_at_added': course.price},
    )
    if created:
        messages.success(request, f'{course.title} added to cart.')
    else:
        messages.info(request, f'{course.title} is already in your cart.')

    next_url = request.GET.get('next')
    return _redirect_to_next_or_default(request, next_url, 'learning:cart_page')


@student_required
@require_POST
def remove_from_cart(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, student=request.user)
    course_title = item.course.title
    item.delete()
    messages.success(request, f'{course_title} removed from cart.')
    return redirect('learning:cart_page')


@student_required
@require_POST
def checkout_cart(request):
    cart_items = list(CartItem.objects.filter(student=request.user).select_related('course'))
    if not cart_items:
        messages.info(request, 'Your cart is empty.')
        return redirect('learning:cart_page')

    payable_items = [item for item in cart_items if item.course.price > 0]
    payment_form = PaymentMethodForm(request.POST or None)
    payment_method = None
    if payable_items:
        if not payment_form.is_valid():
            messages.error(request, 'Please select a payment method and accept the policy.')
            return _render_cart_page(request, payment_form=payment_form)
        payment_method = payment_form.cleaned_data['payment_method']

    now = timezone.now()
    paid_enrolled_count = 0
    free_enrolled_count = 0
    failed_count = 0
    pending_count = 0

    for item in cart_items:
        if Enrollment.objects.filter(student=request.user, course=item.course).exists():
            item.delete()
            continue

        if item.course.price > 0:
            transaction = _create_mock_payment_transaction(
                student=request.user,
                course=item.course,
                amount=item.course.price,
                payment_method=payment_method,
                cleaned_data=payment_form.cleaned_data,
            )
            if transaction.status == MockPaymentTransaction.STATUS_SUCCESS:
                enrollment = Enrollment.objects.create(
                    student=request.user,
                    course=item.course,
                    payment_method=payment_method,
                    payment_status=Enrollment.PAYMENT_PAID,
                    paid_amount=item.course.price,
                    payment_reference=transaction.transaction_id,
                    payment_at=now,
                )
                transaction.enrollment = enrollment
                transaction.save(update_fields=['enrollment', 'updated_at'])
                paid_enrolled_count += 1
                item.delete()
            elif transaction.status == MockPaymentTransaction.STATUS_PENDING:
                pending_count += 1
            else:
                failed_count += 1
        else:
            Enrollment.objects.create(
                student=request.user,
                course=item.course,
                payment_status=Enrollment.PAYMENT_FREE,
                paid_amount=0,
            )
            free_enrolled_count += 1
            item.delete()

    total_enrolled = paid_enrolled_count + free_enrolled_count
    if total_enrolled:
        if paid_enrolled_count:
            method_label = dict(Enrollment.PAYMENT_METHOD_CHOICES).get(payment_method)
            messages.success(
                request,
                f'Mock payment successful via {method_label}. Enrolled {paid_enrolled_count} paid and {free_enrolled_count} free course(s).',
            )
        else:
            messages.success(request, f'Enrolled {free_enrolled_count} free course(s) from cart.')
    elif not (failed_count or pending_count):
        messages.info(request, 'No new course was enrolled from cart.')
    if failed_count:
        messages.error(request, f'{failed_count} payment(s) failed in mock gateway. Those courses are still in cart.')
    if pending_count:
        messages.warning(request, f'{pending_count} payment(s) are pending. Retry checkout later.')

    if failed_count or pending_count:
        return redirect('learning:cart_page')
    return redirect('learning:my_learning')


@student_required
def enroll_course(request, slug):
    course = get_object_or_404(Course, slug=slug, is_published=True)

    existing_enrollment = Enrollment.objects.filter(student=request.user, course=course).first()
    if existing_enrollment:
        messages.info(request, f'You are already enrolled in {course.title}.')
        return redirect('learning:enrolled_course_detail', slug=course.slug)

    if course.price <= 0:
        Enrollment.objects.create(
            student=request.user,
            course=course,
            payment_status=Enrollment.PAYMENT_FREE,
            paid_amount=0,
        )
        CartItem.objects.filter(student=request.user, course=course).delete()
        messages.success(request, f'You are now enrolled in {course.title}.')
        return redirect('learning:enrolled_course_detail', slug=course.slug)

    form = PaymentMethodForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        payment_method = form.cleaned_data['payment_method']
        transaction = _create_mock_payment_transaction(
            student=request.user,
            course=course,
            amount=course.price,
            payment_method=payment_method,
            cleaned_data=form.cleaned_data,
        )
        if transaction.status == MockPaymentTransaction.STATUS_SUCCESS:
            enrollment = Enrollment.objects.create(
                student=request.user,
                course=course,
                payment_method=payment_method,
                payment_status=Enrollment.PAYMENT_PAID,
                paid_amount=course.price,
                payment_reference=transaction.transaction_id,
                payment_at=timezone.now(),
            )
            transaction.enrollment = enrollment
            transaction.save(update_fields=['enrollment', 'updated_at'])
            CartItem.objects.filter(student=request.user, course=course).delete()
            messages.success(
                request,
                f'Mock payment successful via {dict(Enrollment.PAYMENT_METHOD_CHOICES).get(payment_method)}. Enrollment completed.',
            )
            return redirect('learning:enrolled_course_detail', slug=course.slug)

        if transaction.status == MockPaymentTransaction.STATUS_PENDING:
            messages.warning(
                request,
                f'Payment is pending in mock gateway (Txn: {transaction.transaction_id}). Please retry or check payment history.',
            )
        else:
            messages.error(
                request,
                f'Payment failed in mock gateway (Txn: {transaction.transaction_id}). Please retry with another method.',
            )
        return redirect('learning:enroll_course', slug=course.slug)
    if request.method == 'POST':
        messages.error(request, 'Please select a payment method and accept the policy.')

    return render(
        request,
        'student/payment_checkout.html',
        {
            'course': course,
            'payment_form': form,
        },
    )


@student_required
def enrolled_course_detail(request, slug):
    enrollment = get_object_or_404(
        Enrollment.objects.select_related('course').prefetch_related('course__sections__lessons__resources'),
        student=request.user,
        course__slug=slug,
    )

    course_quiz = (
        Quiz.objects.filter(lesson__section__course=enrollment.course, is_active=True)
        .prefetch_related('questions')
        .order_by('-created_at')
        .first()
    )
    latest_quiz_result = None
    if course_quiz:
        latest_quiz_result = Result.objects.filter(student=request.user, quiz=course_quiz).first()

    review_form = ReviewForm()
    existing_review = Review.objects.filter(course=enrollment.course, student=request.user).first()
    has_certificate = Certificate.objects.filter(enrollment=enrollment).exists()
    performance_prediction = predict_student_performance(request.user)
    optimized_learning_path = build_learning_path(enrollment)
    video_summary = build_video_summary(enrollment.course)
    engagement_form = EngagementSnapshotForm()
    plagiarism_form = AssignmentSubmissionForm()
    recent_snapshots = EngagementSnapshot.objects.filter(
        student=request.user,
        course=enrollment.course,
    )[:3]
    recent_submissions = AssignmentSubmission.objects.filter(
        student=request.user,
        course=enrollment.course,
    )[:3]

    return render(
        request,
        'student/enrolled_course_detail.html',
        {
            'enrollment': enrollment,
            'course_quiz': course_quiz,
            'latest_quiz_result': latest_quiz_result,
            'has_certificate': has_certificate,
            'review_form': review_form,
            'existing_review': existing_review,
            'performance_prediction': performance_prediction,
            'optimized_learning_path': optimized_learning_path,
            'video_summary': video_summary,
            'engagement_form': engagement_form,
            'plagiarism_form': plagiarism_form,
            'recent_snapshots': recent_snapshots,
            'recent_submissions': recent_submissions,
        },
    )


@student_required
@require_POST
def mark_course_video_complete(request, slug):
    enrollment = get_object_or_404(
        Enrollment.objects.select_related('course'),
        student=request.user,
        course__slug=slug,
    )

    if enrollment.progress_percentage < Decimal('100.00'):
        enrollment.progress_percentage = Decimal('100.00')
        enrollment.status = Enrollment.COMPLETED
        enrollment.save(update_fields=['progress_percentage', 'status', 'updated_at'])

    certificate = issue_certificate_if_eligible(enrollment)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if is_ajax:
        return JsonResponse(
            {
                'ok': True,
                'progress_percentage': float(enrollment.progress_percentage),
                'certificate_no': certificate.certificate_no if certificate else None,
            }
        )

    messages.success(request, 'Video completed. Course progress updated.')
    return redirect('learning:enrolled_course_detail', slug=slug)


@student_required
@require_POST
def mark_lesson_complete(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)
    enrollment = get_object_or_404(Enrollment, student=request.user, course=lesson.section.course)

    lesson_progress, _ = LessonProgress.objects.get_or_create(enrollment=enrollment, lesson=lesson)
    was_already_completed = lesson_progress.is_completed
    had_certificate = Certificate.objects.filter(enrollment=enrollment).exists()

    if not was_already_completed:
        lesson_progress.is_completed = True
        if lesson_progress.completed_at is None:
            lesson_progress.completed_at = timezone.now()
        lesson_progress.save(update_fields=['is_completed', 'completed_at', 'updated_at'])

    progress = recalculate_course_progress(enrollment)
    certificate = issue_certificate_if_eligible(enrollment) if progress >= 100 else None
    certificate_just_issued = bool(certificate and not had_certificate)

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if is_ajax:
        return JsonResponse(
            {
                'ok': True,
                'lesson_id': lesson.id,
                'was_already_completed': was_already_completed,
                'progress_percentage': float(progress),
                'certificate_no': certificate.certificate_no if certificate else None,
                'certificate_just_issued': certificate_just_issued,
            }
        )

    if was_already_completed:
        messages.info(request, f'Lesson already completed. Current progress: {progress}%')
    else:
        messages.success(request, f'Lesson marked complete. Current progress: {progress}%')

    if certificate_just_issued:
        messages.success(request, f'Congratulations! Certificate generated: {certificate.certificate_no}')

    return redirect('learning:enrolled_course_detail', slug=enrollment.course.slug)


@student_required
def attempt_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz.objects.prefetch_related('questions__options'), id=quiz_id, is_active=True)
    enrollment = get_object_or_404(Enrollment, student=request.user, course=quiz.lesson.section.course)

    if request.method == 'POST':
        answers = {}
        for question in quiz.questions.all():
            selected = request.POST.get(f'question_{question.id}')
            if selected:
                answers[str(question.id)] = int(selected)

        result = evaluate_quiz_submission(student=request.user, quiz=quiz, answers=answers)
        certificate_generated = False
        if result.is_passed:
            if enrollment.progress_percentage < 100:
                enrollment.progress_percentage = Decimal('100.00')
                enrollment.status = Enrollment.COMPLETED
                enrollment.save(update_fields=['progress_percentage', 'status', 'updated_at'])
            certificate_generated = bool(issue_certificate_if_eligible(enrollment))
        messages.success(request, f'Quiz submitted. Your score is {result.score_percentage}%.')
        if result.is_passed and certificate_generated:
            messages.success(request, 'Congratulations! Your certificate is now available.')
        return redirect('learning:quiz_result', result_id=result.id)

    return render(
        request,
        'student/quiz_attempt.html',
        {
            'quiz': quiz,
            'enrollment': enrollment,
            'questions': quiz.questions.all(),
        },
    )


@student_required
def quiz_result(request, result_id):
    result = get_object_or_404(Result.objects.select_related('quiz', 'student'), id=result_id, student=request.user)
    return render(request, 'student/quiz_result.html', {'result': result})


@student_required
def submit_review(request, slug):
    course = get_object_or_404(Course, slug=slug, is_published=True)
    get_object_or_404(Enrollment, student=request.user, course=course)

    existing_review = Review.objects.filter(course=course, student=request.user).first()
    form = ReviewForm(request.POST or None, instance=existing_review)

    if request.method == 'POST' and form.is_valid():
        review = form.save(commit=False)
        review.course = course
        review.student = request.user
        review.save()
        messages.success(request, 'Your review has been submitted.')
    elif request.method == 'POST':
        messages.error(request, 'Unable to submit review. Please check the form.')

    return redirect('learning:enrolled_course_detail', slug=course.slug)


@student_required
def certificate_page(request, enrollment_id):
    enrollment = get_object_or_404(Enrollment, id=enrollment_id, student=request.user)
    certificate = issue_certificate_if_eligible(enrollment)
    if not certificate:
        messages.warning(request, 'Certificate is available only after passing the course quiz.')
        return redirect('learning:enrolled_course_detail', slug=enrollment.course.slug)

    return render(request, 'student/certificate.html', {'certificate': certificate, 'enrollment': enrollment})


@student_required
def certificates_list(request):
    certificates = Certificate.objects.filter(enrollment__student=request.user).select_related('enrollment__course')
    return render(request, 'student/certificates.html', {'certificates': certificates})


@student_required
def payment_history(request):
    payments = MockPaymentTransaction.objects.filter(student=request.user).select_related('course')
    paginator = Paginator(payments, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'student/payment_history.html', {'page_obj': page_obj})


@student_required
@require_POST
def engagement_analysis(request, slug):
    enrollment = get_object_or_404(Enrollment, student=request.user, course__slug=slug)
    form = EngagementSnapshotForm(request.POST or None, request.FILES or None)
    if form.is_valid() and form.cleaned_data.get('image'):
        snapshot = analyze_engagement_snapshot(
            student=request.user,
            course=enrollment.course,
            image_file=form.cleaned_data['image'],
        )
        messages.success(
            request,
            f'Engagement detected as {snapshot.get_detected_emotion_display()} with {snapshot.engagement_score}% engagement score.',
        )
    else:
        messages.error(request, 'Please upload a face snapshot to run engagement analysis.')
    return redirect('learning:enrolled_course_detail', slug=enrollment.course.slug)


@student_required
@require_POST
def delete_engagement_snapshot(request, snapshot_id):
    snapshot = EngagementSnapshot.objects.select_related('course').filter(id=snapshot_id, student=request.user).first()
    if not snapshot:
        messages.info(request, 'That snapshot is no longer available or does not belong to your account.')
        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
        if next_url and url_has_allowed_host_and_scheme(next_url, {request.get_host()}, require_https=request.is_secure()):
            return redirect(next_url)
        return redirect('learning:my_learning')

    course_slug = snapshot.course.slug
    snapshot.delete()
    messages.success(request, 'Past engagement snapshot deleted.')
    return redirect('learning:enrolled_course_detail', slug=course_slug)


@student_required
@require_POST
def plagiarism_check(request, slug):
    enrollment = get_object_or_404(Enrollment, student=request.user, course__slug=slug)
    form = AssignmentSubmissionForm(request.POST or None)
    if form.is_valid():
        submission = analyze_plagiarism_submission(
            student=request.user,
            course=enrollment.course,
            title=form.cleaned_data['title'],
            content=form.cleaned_data['content'],
        )
        if submission.is_flagged:
            messages.warning(
                request,
                f'Plagiarism score: {submission.plagiarism_score}%. Please revise the answer before final submission.',
            )
        else:
            messages.success(request, f'Plagiarism score: {submission.plagiarism_score}%. Similarity looks acceptable.')
    else:
        messages.error(request, 'Please provide a title and answer text for plagiarism analysis.')
    return redirect('learning:enrolled_course_detail', slug=enrollment.course.slug)


@student_required
def wishlist_toggle(request, slug):
    course = get_object_or_404(Course, slug=slug, is_published=True)
    wishlist, created = Wishlist.objects.get_or_create(student=request.user, course=course)
    if created:
        messages.success(request, f'{course.title} added to wishlist.')
    else:
        wishlist.delete()
        messages.info(request, f'{course.title} removed from wishlist.')
    next_url = request.GET.get('next')
    return _redirect_to_next_or_default(request, next_url, 'courses:course_detail', slug=course.slug)


@login_required
def download_resource(request, resource_id):
    resource = get_object_or_404(LessonResource, id=resource_id)

    if request.user.is_superuser or request.user.role == 'admin':
        pass
    elif request.user.role == 'instructor' and resource.lesson.section.course.instructor_id == request.user.id:
        pass
    elif request.user.role == 'student':
        get_object_or_404(Enrollment, student=request.user, course=resource.lesson.section.course)
    else:
        messages.error(request, 'You are not authorized to access this resource.')
        return redirect('core:home')

    if resource.file:
        return redirect(resource.file.url)

    if resource.external_url:
        return redirect(resource.external_url)

    messages.warning(request, 'Resource is currently unavailable.')
    return redirect('learning:enrolled_course_detail', slug=resource.lesson.section.course.slug)
