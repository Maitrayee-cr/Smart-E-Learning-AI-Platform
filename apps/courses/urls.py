from django.urls import path

from . import views

app_name = 'courses'

urlpatterns = [
    path('', views.course_list, name='course_list'),
    path('categories/', views.category_list, name='category_list'),
    path('instructor/dashboard/', views.instructor_dashboard, name='instructor_dashboard'),
    path('instructor/manage/', views.instructor_courses, name='instructor_courses'),
    path('instructor/students/', views.instructor_students, name='instructor_students'),
    path('instructor/add/', views.course_create, name='course_create'),
    path('instructor/<slug:slug>/edit/', views.course_edit, name='course_edit'),
    path('instructor/<slug:slug>/delete/', views.course_delete, name='course_delete'),
    path('instructor/<slug:slug>/curriculum/', views.course_curriculum, name='course_curriculum'),
    path('instructor/<slug:course_slug>/sections/add/', views.section_create, name='section_create'),
    path('instructor/<slug:course_slug>/sections/<int:section_id>/edit/', views.section_edit, name='section_edit'),
    path('instructor/<slug:course_slug>/sections/<int:section_id>/delete/', views.section_delete, name='section_delete'),
    path('instructor/<slug:course_slug>/sections/<int:section_id>/lessons/add/', views.lesson_create, name='lesson_create'),
    path(
        'instructor/<slug:course_slug>/sections/<int:section_id>/lessons/<int:lesson_id>/edit/',
        views.lesson_edit,
        name='lesson_edit',
    ),
    path(
        'instructor/<slug:course_slug>/sections/<int:section_id>/lessons/<int:lesson_id>/delete/',
        views.lesson_delete,
        name='lesson_delete',
    ),
    path(
        'instructor/<slug:course_slug>/sections/<int:section_id>/lessons/<int:lesson_id>/resources/add/',
        views.resource_add,
        name='resource_add',
    ),
    path(
        'instructor/<slug:course_slug>/sections/<int:section_id>/lessons/<int:lesson_id>/quiz/',
        views.quiz_manage,
        name='quiz_manage',
    ),
    path(
        'instructor/<slug:course_slug>/sections/<int:section_id>/lessons/<int:lesson_id>/quiz/ai-generate/',
        views.ai_generate_quiz,
        name='ai_generate_quiz',
    ),
    path('instructor/quiz/<int:quiz_id>/questions/add/', views.question_add, name='question_add'),
    path(
        'instructor/quiz/<int:quiz_id>/questions/<int:question_id>/delete/',
        views.question_delete,
        name='question_delete',
    ),
    path('<slug:slug>/', views.course_detail, name='course_detail'),
]
