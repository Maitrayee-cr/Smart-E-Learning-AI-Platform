from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('faq/', views.faq_page, name='faq'),
    path('contact/', views.contact, name='contact'),
    path('ai-chatbot/reply/', views.chatbot_reply, name='chatbot_reply'),
    path('instructors/', views.instructor_list, name='instructor_list'),
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/users/', views.manage_users, name='manage_users'),
    path('admin/categories/', views.manage_categories, name='manage_categories'),
    path('admin/courses/', views.manage_courses, name='manage_courses'),
    path('admin/enrollments/', views.manage_enrollments, name='manage_enrollments'),
    path('admin/reviews/', views.manage_reviews, name='manage_reviews'),
    path('admin/messages/', views.manage_messages, name='manage_messages'),
]
