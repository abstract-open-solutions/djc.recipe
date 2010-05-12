import imp, sys

from django.core.management import setup_environ

def main(settings_file, logfile=None):
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
        import datetime
        class logger(object):
            def __init__(self, logfile):
                self.logfile = logfile

            def write(self, data):
                self.log(data)

            def writeline(self, data):
                self.log(data)

            def log(self, msg):
                line = '%s - %s\n' % (
                    datetime.datetime.now().strftime('%Y%m%d %H:%M:%S'), msg)
                fp = open(self.logfile, 'a')
                try:
                    fp.write(line)
                finally:
                    fp.close()
        sys.stdout = sys.stderr = logger(logfile)

    from django.core.handlers.wsgi import WSGIHandler

    # Run WSGI handler for the application
    return WSGIHandler()
