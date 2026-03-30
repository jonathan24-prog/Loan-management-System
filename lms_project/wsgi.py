"""
WSGI config for lms_project project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lms_project.settings')




import sys
from django.core.wsgi import get_wsgi_application

class IgnoreBrokenPipeMiddleware:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        try:
            return self.app(environ, start_response)
        except (BrokenPipeError, ConnectionResetError):
            # Ignore client disconnects
            return []

application = get_wsgi_application()
application = IgnoreBrokenPipeMiddleware(application)