from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect



def role_required(*allowed_roles):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            user = request.user
            if user.is_superuser or getattr(user, 'role', None) in allowed_roles:
                return view_func(request, *args, **kwargs)
            messages.error(request, 'You are not authorized to access this page.')
            return redirect('accounts:post_login_redirect')

        return _wrapped_view

    return decorator


student_required = role_required('student')
instructor_required = role_required('instructor')
admin_required = role_required('admin')
