from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_choice, name='register'),
    path('register/student/', views.register_student, name='register_student'),
    path('register/instructor/', views.register_instructor, name='register_instructor'),
    path('profile/', views.profile_view, name='profile'),
    path('change-password/', views.change_password_view, name='change_password'),
    path('redirect/', views.post_login_redirect, name='post_login_redirect'),
]
