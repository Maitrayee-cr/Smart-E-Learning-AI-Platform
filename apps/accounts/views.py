from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import (
    InstructorProfileForm,
    InstructorRegistrationForm,
    StudentProfileForm,
    StudentRegistrationForm,
    UserLoginForm,
    UserPasswordChangeForm,
    UserProfileForm,
)
from .models import InstructorProfile, StudentProfile, User


def register_choice(request):
    if request.user.is_authenticated:
        return redirect('accounts:post_login_redirect')
    return render(request, 'accounts/register.html')


def register_student(request):
    if request.user.is_authenticated:
        return redirect('accounts:post_login_redirect')

    form = StudentRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Student account created successfully. Please log in.')
        return redirect('accounts:login')
    return render(request, 'accounts/register_student.html', {'form': form})


def register_instructor(request):
    if request.user.is_authenticated:
        return redirect('accounts:post_login_redirect')

    form = InstructorRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Instructor account created successfully. Please log in.')
        return redirect('accounts:login')
    return render(request, 'accounts/register_instructor.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:post_login_redirect')

    form = UserLoginForm(request, data=request.POST or None)
    if request.method == 'POST':
        identifier = (request.POST.get('username') or '').strip()
        password = request.POST.get('password') or ''

        if not identifier or not password:
            messages.error(request, 'Please enter username/email and password.')
            return render(request, 'accounts/login.html', {'form': form})

        # Support login with either username or email.
        username = identifier
        if '@' in identifier:
            matched_user = User.objects.filter(email__iexact=identifier).only('username').first()
            if matched_user:
                username = matched_user.username

        user = authenticate(request, username=username, password=password)
        if user and user.is_active:
            login(request, user)
            messages.success(request, f'Welcome back, {user.first_name or user.username}!')
            return redirect('accounts:post_login_redirect')

        messages.error(request, 'Invalid credentials. Please try again.')

    return render(request, 'accounts/login.html', {'form': form})


@login_required
def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('core:home')


@login_required
def post_login_redirect(request):
    user = request.user
    if user.is_superuser or user.role == User.ADMIN:
        return redirect('core:admin_dashboard')
    if user.role == User.INSTRUCTOR:
        return redirect('courses:instructor_dashboard')
    return redirect('learning:student_dashboard')


@login_required
def profile_view(request):
    user_form = UserProfileForm(request.POST or None, request.FILES or None, instance=request.user)
    profile_form = None

    if request.user.role == User.STUDENT:
        profile_instance, _ = StudentProfile.objects.get_or_create(user=request.user)
        profile_form = StudentProfileForm(request.POST or None, instance=profile_instance)
    elif request.user.role == User.INSTRUCTOR:
        profile_instance, _ = InstructorProfile.objects.get_or_create(user=request.user)
        profile_form = InstructorProfileForm(request.POST or None, instance=profile_instance)

    if request.method == 'POST':
        if profile_form and user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('accounts:profile')

        if not profile_form and user_form.is_valid():
            user_form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('accounts:profile')

        messages.error(request, 'Please fix the highlighted errors and try again.')

    return render(
        request,
        'accounts/profile.html',
        {
            'user_form': user_form,
            'profile_form': profile_form,
        },
    )


@login_required
def change_password_view(request):
    form = UserPasswordChangeForm(user=request.user, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, 'Your password has been changed successfully.')
        return redirect('accounts:profile')
    return render(request, 'accounts/change_password.html', {'form': form})
