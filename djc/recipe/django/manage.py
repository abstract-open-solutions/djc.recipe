import imp
from django.core import management

def main(settings_file):
    try:
        imp.acquire_lock()
        mod = imp.load_source('_django_settings', settings_file)
    except Exception, e:
        imp.release_lock()
        import sys
        sys.stderr.write("Error loading the settings module '%s': %s"
                            % (settings_file, e))
        return sys.exit(1)
    
    imp.release_lock()
    management.execute_manager(mod)
    
