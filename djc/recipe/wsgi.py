import logging
from utils import setup_django


def main(settings, logfile=None, loglevel=None):
    setup_django(settings)

    if logfile:
        kwargs = {
            'filename': logfile
        }
        if loglevel and hasattr(logging, loglevel):
            kwargs['level'] = getattr(logging, loglevel)
        logging.basicConfig(**kwargs)

    from django.core.handlers.wsgi import WSGIHandler

    # Run WSGI handler for the application
    return WSGIHandler()
