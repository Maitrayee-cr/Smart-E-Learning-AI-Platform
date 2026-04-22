import json

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.db.utils import OperationalError, ProgrammingError
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.decorators import instructor_required
from apps.learning.ai_features import build_instructor_ai_analytics, create_or_replace_generated_quiz
from apps.learning.models import CartItem, Enrollment, Wishlist
from apps.learning.services import build_course_ai_fit, get_personalized_recommendations

from .forms import (
    AIQuizGeneratorForm,
    CourseFilterForm,
    CourseForm,
    CourseSectionForm,
    LessonForm,
    LessonResourceForm,
    QuestionForm,
    QuizForm,
)
from .models import Category, Course, CourseSection, Lesson, LessonResource, Option, Question, Quiz


def course_list(request):
    excluded_categories = ['School Courses', 'Commerce', 'Aptitude']
    courses = (
        Course.objects.filter(is_published=True)
        .exclude(category__name__in=excluded_categories)
        .select_related('instructor', 'category')
        .annotate(avg_rating=Avg('reviews__rating'))
        .order_by('-created_at')
    )
    form = CourseFilterForm(request.GET or None)

    if form.is_valid():
        search_term = form.cleaned_data.get('q')
        category = form.cleaned_data.get('category')
        level = form.cleaned_data.get('level')
        pricing = form.cleaned_data.get('pricing')
        sort = form.cleaned_data.get('sort')

        if search_term:
            courses = courses.filter(
                Q(title__icontains=search_term)
                | Q(category__name__icontains=search_term)
                | Q(instructor__first_name__icontains=search_term)
                | Q(instructor__last_name__icontains=search_term)
            )

        if category:
            courses = courses.filter(category=category)

        if level:
            courses = courses.filter(level=level)

        if pricing == 'free':
            courses = courses.filter(price=0)
        elif pricing == 'paid':
            courses = courses.filter(price__gt=0)

        if sort == 'rating':
            courses = courses.order_by('-avg_rating', '-created_at')
        elif sort == 'price_asc':
            courses = courses.order_by('price', '-created_at')
        elif sort == 'price_desc':
            courses = courses.order_by('-price', '-created_at')
        else:
            courses = courses.order_by('-created_at')

    paginator = Paginator(courses, 9)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(
        request,
        'public/courses.html',
        {
            'form': form,
            'page_obj': page_obj,
        },
    )


def category_list(request):
    categories = (
        Category.objects.filter(is_active=True)
        .exclude(name__iexact='School Courses')
        .exclude(name__iexact='Commerce')
        .exclude(name__iexact='Aptitude')
        .annotate(total_courses=Count('courses'))
        .order_by('-total_courses')
    )
    return render(request, 'public/categories.html', {'categories': categories})


def course_detail(request, slug):
    excluded_categories = ['School Courses', 'Commerce', 'Aptitude']
    course = get_object_or_404(
        Course.objects.select_related('instructor', 'category').prefetch_related(
            'sections__lessons__resources',
        ).exclude(category__name__in=excluded_categories),
        slug=slug,
        is_published=True,
    )

    related_courses = (
        Course.objects.filter(category=course.category, is_published=True)
        .exclude(id=course.id)
        .select_related('instructor')[:4]
    )
    reviews = course.reviews.filter(is_approved=True).select_related('student')[:8]
    course_quiz = (
        Quiz.objects.filter(lesson__section__course=course, is_active=True)
        .prefetch_related('questions')
        .order_by('-created_at')
        .first()
    )

    enrollment = None
    is_in_wishlist = False
    is_in_cart = False
    ai_course_fit = None
    ai_related_recommendations = []
    if request.user.is_authenticated and request.user.role == 'student':
        try:
            enrollment = Enrollment.objects.filter(student=request.user, course=course).first()
            is_in_wishlist = Wishlist.objects.filter(student=request.user, course=course).exists()
            is_in_cart = CartItem.objects.filter(student=request.user, course=course).exists()
            ai_course_fit = build_course_ai_fit(request.user, course)
            ai_related_recommendations = [
                item for item in get_personalized_recommendations(request.user, limit=4) if item['course'].id != course.id
            ][:3]
        except (OperationalError, ProgrammingError):
            enrollment = None
            is_in_wishlist = False
            is_in_cart = False
            ai_course_fit = None
            ai_related_recommendations = []

    return render(
        request,
        'public/course_detail.html',
        {
            'course': course,
            'related_courses': related_courses,
            'reviews': reviews,
            'course_quiz': course_quiz,
            'enrollment': enrollment,
            'is_in_wishlist': is_in_wishlist,
            'is_in_cart': is_in_cart,
            'ai_course_fit': ai_course_fit,
            'ai_related_recommendations': ai_related_recommendations,
        },
    )


@instructor_required
def instructor_dashboard(request):
    courses = Course.objects.filter(instructor=request.user)
    ai_analytics = build_instructor_ai_analytics(request.user)
    analytics = {
        'total_courses': courses.count(),
        'published_courses': courses.filter(is_published=True).count(),
        'total_students': Enrollment.objects.filter(course__instructor=request.user).count(),
        'avg_rating': (
            courses.aggregate(rating=Avg('reviews__rating')).get('rating') or 0
        ),
    }

    top_courses = courses.annotate(student_count=Count('enrollments')).order_by('-student_count')[:5]
    chart_data = {
        'labels': [course.title for course in top_courses],
        'values': [course.student_count for course in top_courses],
    }

    return render(
        request,
        'instructor/dashboard.html',
        {
            'analytics': analytics,
            'top_courses': top_courses,
            'ai_analytics': ai_analytics,
            'chart_data_json': json.dumps(chart_data),
            'ai_performance_chart_json': json.dumps(ai_analytics['performance_chart']),
            'ai_engagement_chart_json': json.dumps(ai_analytics['engagement_chart']),
        },
    )


@instructor_required
def instructor_courses(request):
    courses = Course.objects.filter(instructor=request.user).select_related('category').order_by('-created_at')
    return render(request, 'instructor/manage_courses.html', {'courses': courses})


@instructor_required
def instructor_students(request):
    query = request.GET.get('q', '').strip()
    enrollments = Enrollment.objects.filter(course__instructor=request.user).select_related('student', 'course')
    if query:
        enrollments = enrollments.filter(
            Q(student__username__icontains=query)
            | Q(student__first_name__icontains=query)
            | Q(student__last_name__icontains=query)
            | Q(course__title__icontains=query)
        )

    paginator = Paginator(enrollments.order_by('-enrolled_at'), 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'instructor/students_enrolled.html', {'page_obj': page_obj, 'query': query})


@instructor_required
def course_create(request):
    form = CourseForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        course = form.save(commit=False)
        course.instructor = request.user
        course.save()
        messages.success(request, 'Course created successfully.')
        return redirect('courses:instructor_courses')
    return render(request, 'instructor/course_form.html', {'form': form, 'title': 'Add Course'})


@instructor_required
def course_edit(request, slug):
    course = get_object_or_404(Course, slug=slug, instructor=request.user)
    form = CourseForm(request.POST or None, request.FILES or None, instance=course)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Course updated successfully.')
        return redirect('courses:instructor_courses')
    return render(request, 'instructor/course_form.html', {'form': form, 'title': 'Edit Course', 'course': course})


@instructor_required
def course_delete(request, slug):
    course = get_object_or_404(Course, slug=slug, instructor=request.user)
    if request.method == 'POST':
        course.delete()
        messages.success(request, 'Course deleted successfully.')
        return redirect('courses:instructor_courses')
    return render(request, 'instructor/course_delete_confirm.html', {'course': course})


@instructor_required
def course_curriculum(request, slug):
    course = get_object_or_404(Course, slug=slug, instructor=request.user)
    sections = course.sections.prefetch_related('lessons__resources').all()

    section_form = CourseSectionForm()
    lesson_form = LessonForm()
    resource_form = LessonResourceForm()

    return render(
        request,
        'instructor/manage_lessons.html',
        {
            'course': course,
            'sections': sections,
            'section_form': section_form,
            'lesson_form': lesson_form,
            'resource_form': resource_form,
        },
    )


@instructor_required
def section_create(request, course_slug):
    course = get_object_or_404(Course, slug=course_slug, instructor=request.user)
    form = CourseSectionForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        section = form.save(commit=False)
        section.course = course
        section.save()
        messages.success(request, 'Module created successfully.')
    else:
        messages.error(request, 'Unable to create module. Please check the form.')
    return redirect('courses:course_curriculum', slug=course.slug)


@instructor_required
def section_edit(request, course_slug, section_id):
    course = get_object_or_404(Course, slug=course_slug, instructor=request.user)
    section = get_object_or_404(CourseSection, id=section_id, course=course)
    form = CourseSectionForm(request.POST or None, instance=section)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Module updated successfully.')
    elif request.method == 'POST':
        messages.error(request, 'Unable to update module.')
    return redirect('courses:course_curriculum', slug=course.slug)


@instructor_required
def section_delete(request, course_slug, section_id):
    course = get_object_or_404(Course, slug=course_slug, instructor=request.user)
    section = get_object_or_404(CourseSection, id=section_id, course=course)
    if request.method == 'POST':
        section.delete()
        messages.success(request, 'Module deleted successfully.')
    return redirect('courses:course_curriculum', slug=course.slug)


@instructor_required
def lesson_create(request, course_slug, section_id):
    course = get_object_or_404(Course, slug=course_slug, instructor=request.user)
    section = get_object_or_404(CourseSection, id=section_id, course=course)
    form = LessonForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        lesson = form.save(commit=False)
        lesson.section = section
        lesson.save()
        messages.success(request, 'Lesson created successfully.')
    else:
        messages.error(request, 'Unable to create lesson.')
    return redirect('courses:course_curriculum', slug=course.slug)


@instructor_required
def lesson_edit(request, course_slug, section_id, lesson_id):
    course = get_object_or_404(Course, slug=course_slug, instructor=request.user)
    section = get_object_or_404(CourseSection, id=section_id, course=course)
    lesson = get_object_or_404(Lesson, id=lesson_id, section=section)
    form = LessonForm(request.POST or None, request.FILES or None, instance=lesson)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Lesson updated successfully.')
    elif request.method == 'POST':
        messages.error(request, 'Unable to update lesson.')
    return redirect('courses:course_curriculum', slug=course.slug)


@instructor_required
def lesson_delete(request, course_slug, section_id, lesson_id):
    course = get_object_or_404(Course, slug=course_slug, instructor=request.user)
    section = get_object_or_404(CourseSection, id=section_id, course=course)
    lesson = get_object_or_404(Lesson, id=lesson_id, section=section)
    if request.method == 'POST':
        lesson.delete()
        messages.success(request, 'Lesson deleted successfully.')
    return redirect('courses:course_curriculum', slug=course.slug)


@instructor_required
def resource_add(request, course_slug, section_id, lesson_id):
    course = get_object_or_404(Course, slug=course_slug, instructor=request.user)
    section = get_object_or_404(CourseSection, id=section_id, course=course)
    lesson = get_object_or_404(Lesson, id=lesson_id, section=section)
    form = LessonResourceForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        resource = form.save(commit=False)
        resource.lesson = lesson
        resource.save()
        messages.success(request, 'Resource added successfully.')
    else:
        messages.error(request, 'Unable to add resource.')
    return redirect('courses:course_curriculum', slug=course.slug)


@instructor_required
def quiz_manage(request, course_slug, section_id, lesson_id):
    course = get_object_or_404(Course, slug=course_slug, instructor=request.user)
    section = get_object_or_404(CourseSection, id=section_id, course=course)
    lesson = get_object_or_404(Lesson, id=lesson_id, section=section)

    quiz = lesson.quizzes.first()
    form = QuizForm(request.POST or None, instance=quiz)

    if request.method == 'POST' and form.is_valid():
        quiz_obj = form.save(commit=False)
        quiz_obj.lesson = lesson
        quiz_obj.save()
        messages.success(request, 'Quiz saved successfully.')
        return redirect('courses:quiz_manage', course_slug=course.slug, section_id=section.id, lesson_id=lesson.id)

    questions = quiz.questions.prefetch_related('options').all() if quiz else []
    question_form = QuestionForm()
    ai_generator_form = AIQuizGeneratorForm()
    return render(
        request,
        'instructor/quiz_manage.html',
        {
            'course': course,
            'section': section,
            'lesson': lesson,
            'quiz': quiz,
            'form': form,
            'question_form': question_form,
            'ai_generator_form': ai_generator_form,
            'questions': questions,
        },
    )


@instructor_required
def question_add(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id, lesson__section__course__instructor=request.user)
    form = QuestionForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        question = form.save(commit=False)
        question.quiz = quiz
        question.save()

        option_texts = [
            form.cleaned_data['option_1'],
            form.cleaned_data['option_2'],
            form.cleaned_data['option_3'],
            form.cleaned_data['option_4'],
        ]
        correct_option = int(form.cleaned_data['correct_option']) - 1

        for idx, option_text in enumerate(option_texts):
            Option.objects.create(question=question, text=option_text, is_correct=idx == correct_option)

        messages.success(request, 'Question added successfully.')
    else:
        messages.error(request, 'Unable to add question.')

    return redirect(
        'courses:quiz_manage',
        course_slug=quiz.lesson.section.course.slug,
        section_id=quiz.lesson.section.id,
        lesson_id=quiz.lesson.id,
    )


@instructor_required
def question_delete(request, quiz_id, question_id):
    quiz = get_object_or_404(Quiz, id=quiz_id, lesson__section__course__instructor=request.user)
    question = get_object_or_404(Question, id=question_id, quiz=quiz)
    if request.method == 'POST':
        question.delete()
        messages.success(request, 'Question deleted successfully.')
    return redirect(
        'courses:quiz_manage',
        course_slug=quiz.lesson.section.course.slug,
        section_id=quiz.lesson.section.id,
        lesson_id=quiz.lesson.id,
    )


@instructor_required
def ai_generate_quiz(request, course_slug, section_id, lesson_id):
    course = get_object_or_404(Course, slug=course_slug, instructor=request.user)
    section = get_object_or_404(CourseSection, id=section_id, course=course)
    lesson = get_object_or_404(Lesson, id=lesson_id, section=section)
    form = AIQuizGeneratorForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        quiz, _ = create_or_replace_generated_quiz(
            lesson=lesson,
            question_count=form.cleaned_data['question_count'],
            difficulty=form.cleaned_data['difficulty'],
            source_text=form.cleaned_data['source_text'],
        )
        messages.success(
            request,
            f'AI quiz generated for {lesson.title}. {quiz.questions.count()} MCQs were created with answer keys and difficulty levels.',
        )
    else:
        messages.error(request, 'Unable to generate the smart quiz. Please check the generator form.')
    return redirect('courses:quiz_manage', course_slug=course.slug, section_id=section.id, lesson_id=lesson.id)
