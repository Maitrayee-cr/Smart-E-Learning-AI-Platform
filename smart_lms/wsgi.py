"""WSGI config for smart_lms project."""

import os
from pathlib import Path

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smart_lms.settings')

application = get_wsgi_application()


def _initialize_vercel_demo_database():
    if not os.getenv('VERCEL'):
        return

    marker_path = Path('/tmp/smart_lms_demo_db_ready')
    if marker_path.exists():
        return

    try:
        from django.core.management import call_command

        call_command('migrate', interactive=False, verbosity=0)
        call_command('seed_demo_data', verbosity=0)
        marker_path.write_text('ready', encoding='utf-8')
    except Exception as exc:  # pragma: no cover - visible in Vercel logs
        print(f'Vercel demo database initialization failed: {exc}')


_initialize_vercel_demo_database()
