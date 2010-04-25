import imp
from django.core.management import setup_environ, ManagementUtility

def main(settings_file):
    import sys
    try:
        imp.acquire_lock()
        mod = imp.load_source('_django_settings', settings_file)
    except Exception, e:
        imp.release_lock()
        sys.stderr.write("Error loading the settings module '%s': %s"
                            % (settings_file, e))
        return sys.exit(1)
    
    imp.release_lock()

    setup_environ(mod, '_django_settings')
    utility = ManagementUtility(sys.argv)
    utility.execute()
    
