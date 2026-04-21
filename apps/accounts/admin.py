from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import InstructorProfile, StudentProfile, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            'Profile Info',
            {
                'fields': ('role', 'phone', 'avatar', 'bio', 'is_email_verified'),
            },
        ),
    )
    list_display = ('username', 'email', 'role', 'is_active', 'date_joined')
    list_filter = ('role', 'is_active', 'is_staff')


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'university', 'semester', 'city')
    search_fields = ('user__username', 'user__email', 'university')


@admin.register(InstructorProfile)
class InstructorProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'headline', 'experience_years', 'approved')
    list_filter = ('approved',)
    search_fields = ('user__username', 'user__email', 'headline')
