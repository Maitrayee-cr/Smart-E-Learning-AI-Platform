from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('', include('apps.core.urls')),
    path('accounts/', include('apps.accounts.urls')),
    path('courses/', include('apps.courses.urls')),
    path('learning/', include('apps.learning.urls')),
    path('admin/', admin.site.urls),
    path('super-admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
