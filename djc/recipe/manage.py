import sys
from django.core.management import ManagementUtility
from utils import setup_django


def main(settings):
    setup_django(settings)
    utility = ManagementUtility(sys.argv)
    utility.execute()
