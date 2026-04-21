from django.db.utils import OperationalError, ProgrammingError

from apps.courses.models import Category, Course


def global_stats(request):
    try:
        context = {
            'nav_categories': (
                Category.objects.filter(is_active=True)
                .exclude(name__iexact='School Courses')
                .exclude(name__iexact='Commerce')
                .exclude(name__iexact='Aptitude')[:8]
            ),
            'featured_courses_count': Course.objects.filter(is_featured=True, is_published=True).count(),
            'nav_cart_count': 0,
            'nav_wishlist_count': 0,
        }
        if request.user.is_authenticated and getattr(request.user, 'role', None) == 'student':
            from apps.learning.models import CartItem, Wishlist

            context['nav_cart_count'] = CartItem.objects.filter(student=request.user).count()
            context['nav_wishlist_count'] = Wishlist.objects.filter(student=request.user).count()
        return context
    except (OperationalError, ProgrammingError):
        # Handles first run before migrations.
        return {
            'nav_categories': [],
            'featured_courses_count': 0,
            'nav_cart_count': 0,
            'nav_wishlist_count': 0,
        }
