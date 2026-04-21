from django.contrib import admin

from .models import Category, Course, Review


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'created_at')
    prepopulated_fields = {'slug': ('name',)}
    list_filter = ('is_active',)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'instructor', 'category', 'price', 'is_published', 'is_featured')
    list_filter = ('is_published', 'is_featured', 'level', 'category')
    search_fields = ('title', 'instructor__username', 'category__name')
    prepopulated_fields = {'slug': ('title',)}


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('course', 'student', 'rating', 'is_approved', 'created_at')
    list_filter = ('rating', 'is_approved')
    search_fields = ('course__title', 'student__username')
