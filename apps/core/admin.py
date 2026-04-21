from django.contrib import admin

from .models import ContactMessage, FAQ, Testimonial


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject', 'is_resolved', 'created_at')
    list_filter = ('is_resolved',)
    search_fields = ('name', 'email', 'subject')


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'order', 'is_active')
    list_filter = ('is_active',)


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ('name', 'designation', 'rating', 'is_featured', 'created_at')
    list_filter = ('rating', 'is_featured')
