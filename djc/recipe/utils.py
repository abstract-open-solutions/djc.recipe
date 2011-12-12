try:
    from importlib import import_module
except ImportError:
    from django.utils.importlib import import_module
from django.core.management import setup_environ


def setup_django(settings):
    mod = import_module(settings)
    setup_environ(mod, settings)
