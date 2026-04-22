import os
import sys
from pathlib import Path

# Add the project directory to the path
project_dir = Path(__file__).parent.parent
sys.path.insert(0, str(project_dir))

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smart_lms.settings')

import django
django.setup()

from smart_lms.wsgi import application

# Export the application for Vercel
def handler(request):
    return application(request)