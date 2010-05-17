# -*- coding: utf-8 -*-
"""
This module contains the tool of djc.recipe.django
"""
import os
from setuptools import setup, find_packages

def read(*rnames):
    return open(os.path.join(os.path.dirname(__file__), *rnames)).read()

version = '0.2'

long_description = (
    read('README.txt')
    + '\n' +
    'Detailed Documentation\n'
    '**********************\n'
    + '\n' +
    read('djc', 'recipe', 'README.txt')
    + '\n' +
    'Contributors\n' 
    '************\n'
    + '\n' +
    read('CONTRIBUTORS.txt')
    + '\n' +
    'Change history\n'
    '**************\n'
    + '\n' + 
    read('CHANGES.txt')
    )
entry_point = 'djc.recipe.recipe:Recipe'
entry_points = {"zc.buildout": ["default = %s" % entry_point]}

tests_require=['zope.testing', 'zc.buildout']

setup(name='djc.recipe',
      version=version,
      description="A Django buildout recipe",
      long_description=long_description,
      # Get more strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      classifiers=[
        'Framework :: Buildout',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: BSD License',
      ],
      keywords='',
      author='Simone Deponti',
      author_email='simone.deponti@abstract.it',
      url='http://open.abstract.it/it/progetti/rilasci-abstract/djc.recipe/',
      license='BSD',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['djc'],
      include_package_data=True,
      zip_safe=False,
      install_requires=['setuptools',
                        'zc.buildout',
                        'zc.recipe.egg',
                        'Tempita',
                        'Django'
                        ],
      tests_require=tests_require,
      extras_require=dict(tests=tests_require),
      test_suite = 'djc.recipe.tests.test_docs.test_suite',
      entry_points=entry_points,
      )
