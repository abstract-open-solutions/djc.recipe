import imp, sys, logging

from django.core.management import setup_environ

def main(settings_file, logfile=None, loglevel=None):
    try:
        imp.acquire_lock()
        mod = imp.load_source('_django_settings', settings_file)
    except Exception, e:
        imp.release_lock()
        sys.stderr.write("Error loading the settings module '%s': %s"
                            % (settings_file, e))
        return sys.exit(1)

    imp.release_lock()
    # Setup settings
    setup_environ(mod, '_django_settings')

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
