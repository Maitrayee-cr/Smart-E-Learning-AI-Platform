import json

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.decorators import admin_required
from apps.courses.forms import CategoryForm
from apps.courses.models import Category, Course, Review
from apps.learning.ai_features import build_platform_ai_analytics
from apps.learning.models import Certificate, Enrollment, Result
from apps.learning.services import get_personalized_recommendations

from .forms import ContactForm
from .models import ContactMessage, FAQ, Testimonial
from .services import build_chatbot_response

User = get_user_model()


def home(request):
    excluded_categories = ['School Courses', 'Commerce', 'Aptitude']
    featured_courses = (
        Course.objects.filter(is_published=True, is_featured=True)
        .exclude(category__name__in=excluded_categories)
        .select_related('category', 'instructor')[:8]
    )
    latest_courses = (
        Course.objects.filter(is_published=True)
        .exclude(category__name__in=excluded_categories)
        .select_related('category', 'instructor')[:8]
    )
    top_categories = (
        Category.objects.filter(is_active=True)
        .exclude(name__iexact='School Courses')
        .exclude(name__iexact='Commerce')
        .exclude(name__iexact='Aptitude')
        .annotate(course_count=Count('courses'))
        .order_by('-course_count')[:8]
    )
    instructors = (
        User.objects.filter(role='instructor', instructor_profile__approved=True)
        .annotate(course_count=Count('instructor_courses'))
        .order_by('-course_count')[:6]
    )
    testimonials = Testimonial.objects.filter(is_featured=True)[:6]

    context = {
        'featured_courses': featured_courses,
        'latest_courses': latest_courses,
        'top_categories': top_categories,
        'instructors': instructors,
        'testimonials': testimonials,
        'personalized_recommendations': [],
        'stats': {
            'students': User.objects.filter(role='student').count(),
            'instructors': User.objects.filter(role='instructor').count(),
            'courses': Course.objects.filter(is_published=True).exclude(category__name__in=excluded_categories).count(),
            'enrollments': Enrollment.objects.count(),
        },
    }
    if request.user.is_authenticated and request.user.role == 'student':
        context['personalized_recommendations'] = get_personalized_recommendations(request.user, limit=4)
    return render(request, 'public/home.html', context)


def about(request):
    return render(request, 'public/about.html')


def faq_page(request):
    faqs = FAQ.objects.filter(is_active=True)
    return render(request, 'public/faq.html', {'faqs': faqs})


def contact(request):
    form = ContactForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Thank you for contacting us. We will get back to you shortly.')
        return redirect('core:contact')
    return render(request, 'public/contact.html', {'form': form})


def instructor_list(request):
    instructors = User.objects.filter(role='instructor', instructor_profile__approved=True).order_by('first_name')
    paginator = Paginator(instructors, 12)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'public/instructors.html', {'page_obj': page_obj})


@require_POST
def chatbot_reply(request):
    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse(
            {
                'reply': 'I could not read that message. Please try again.',
                'chips': ['Recommend courses', 'Show free courses', 'How certificates work'],
                'links': [{'label': 'Courses', 'url': '/courses/'}],
            },
            status=400,
        )

    message = payload.get('message', '')
    response_payload = build_chatbot_response(message, request.user)
    return JsonResponse(response_payload)


@admin_required
def admin_dashboard(request):
    ai_analytics = build_platform_ai_analytics()
    total_revenue = (
        Enrollment.objects.filter(payment_status=Enrollment.PAYMENT_PAID)
        .aggregate(total=Sum('paid_amount'))
        .get('total')
        or 0
    )
    analytics = {
        'total_users': User.objects.count(),
        'total_instructors': User.objects.filter(role='instructor').count(),
        'total_students': User.objects.filter(role='student').count(),
        'total_courses': Course.objects.count(),
        'total_enrollments': Enrollment.objects.count(),
        'total_certificates': Certificate.objects.count(),
        'avg_rating': Review.objects.filter(is_approved=True).aggregate(avg=Avg('rating')).get('avg') or 0,
        'total_quiz_attempts': Result.objects.count(),
        'revenue': total_revenue,
    }

    recent_messages = ContactMessage.objects.all()[:5]
    recent_enrollments = Enrollment.objects.select_related('student', 'course')[:8]

    return render(
        request,
        'admin_portal/dashboard.html',
        {
            'analytics': analytics,
            'ai_analytics': ai_analytics,
            'recent_messages': recent_messages,
            'recent_enrollments': recent_enrollments,
            'chart_data_json': json.dumps(
                {
                    'labels': ['Students', 'Instructors', 'Courses', 'Enrollments', 'Certificates'],
                    'values': [
                        analytics['total_students'],
                        analytics['total_instructors'],
                        analytics['total_courses'],
                        analytics['total_enrollments'],
                        analytics['total_certificates'],
                    ],
                }
            ),
            'ai_performance_chart_json': json.dumps(ai_analytics['performance_chart']),
            'ai_engagement_chart_json': json.dumps(ai_analytics['engagement_chart']),
        },
    )


@admin_required
def manage_users(request):
    query = request.GET.get('q', '').strip()
    role = request.GET.get('role', '').strip()

    users = User.objects.all()
    if query:
        users = users.filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
        )
    if role:
        users = users.filter(role=role)

    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        new_role = request.POST.get('new_role')
        target_user = get_object_or_404(User, id=user_id)
        if new_role in {User.STUDENT, User.INSTRUCTOR, User.ADMIN}:
            target_user.role = new_role
            target_user.save(update_fields=['role'])
            messages.success(request, f'Role updated for {target_user.username}.')
        return redirect('core:manage_users')

    paginator = Paginator(users.order_by('-date_joined'), 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_portal/manage_users.html', {'page_obj': page_obj, 'query': query, 'role': role})


@admin_required
def manage_categories(request):
    form = CategoryForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Category saved successfully.')
        return redirect('core:manage_categories')

    categories = Category.objects.all().order_by('name')
    return render(request, 'admin_portal/manage_categories.html', {'form': form, 'categories': categories})


@admin_required
def manage_courses(request):
    courses = Course.objects.select_related('instructor', 'category').all().order_by('-created_at')

    if request.method == 'POST':
        course_id = request.POST.get('course_id')
        action = request.POST.get('action')
        course = get_object_or_404(Course, id=course_id)

        if action == 'publish':
            course.is_published = True
        elif action == 'unpublish':
            course.is_published = False
        elif action == 'feature':
            course.is_featured = True
        elif action == 'unfeature':
            course.is_featured = False
        course.save(update_fields=['is_published', 'is_featured'])
        messages.success(request, f'Course "{course.title}" updated.')
        return redirect('core:manage_courses')

    paginator = Paginator(courses, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_portal/manage_courses.html', {'page_obj': page_obj})


@admin_required
def manage_enrollments(request):
    enrollments = Enrollment.objects.select_related('student', 'course').all().order_by('-enrolled_at')
    paginator = Paginator(enrollments, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_portal/manage_enrollments.html', {'page_obj': page_obj})


@admin_required
def manage_reviews(request):
    reviews = Review.objects.select_related('student', 'course').all().order_by('-created_at')

    if request.method == 'POST':
        review_id = request.POST.get('review_id')
        action = request.POST.get('action')
        review = get_object_or_404(Review, id=review_id)
        review.is_approved = action == 'approve'
        review.save(update_fields=['is_approved'])
        messages.success(request, 'Review status updated.')
        return redirect('core:manage_reviews')

    paginator = Paginator(reviews, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_portal/manage_reviews.html', {'page_obj': page_obj})


@admin_required
def manage_messages(request):
    messages_qs = ContactMessage.objects.all().order_by('-created_at')

    if request.method == 'POST':
        message_id = request.POST.get('message_id')
        msg = get_object_or_404(ContactMessage, id=message_id)
        msg.is_resolved = not msg.is_resolved
        msg.save(update_fields=['is_resolved'])
        messages.success(request, 'Message status updated.')
        return redirect('core:manage_messages')

    paginator = Paginator(messages_qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_portal/manage_messages.html', {'page_obj': page_obj})
