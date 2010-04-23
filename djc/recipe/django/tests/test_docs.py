# -*- coding: utf-8 -*-
"""
Doctest runner for 'djc.recipe.django'.
"""
__docformat__ = 'restructuredtext'

import unittest, os
import zc.buildout.tests
import zc.buildout.testing

from zope.testing import doctest, renormalizing

optionflags =  (doctest.ELLIPSIS |
                doctest.NORMALIZE_WHITESPACE |
                doctest.REPORT_ONLY_FIRST_FAILURE)

def setUp(test):
    normpath, join, dirname = os.path.normpath, os.path.join, os.path.dirname
    zc.buildout.testing.buildoutSetUp(test)
    zc.buildout.testing.install_develop('djc.recipe.django', test)
    packages = join(test.globs['sample_buildout'], 'packages')
    zc.buildout.testing.mkdir(packages)
    zc.buildout.testing.sdist(
        normpath(join(dirname(__file__), '..', 'testing')),
        packages
    )

def test_suite():
    suite = unittest.TestSuite((
            doctest.DocFileSuite(
                '../README.txt',
                setUp=setUp,
                tearDown=zc.buildout.testing.buildoutTearDown,
                optionflags=optionflags,
                checker=renormalizing.RENormalizing([
                        # If want to clean up the doctest output you
                        # can register additional regexp normalizers
                        # here. The format is a two-tuple with the RE
                        # as the first item and the replacement as the
                        # second item, e.g.
                        # (re.compile('my-[rR]eg[eE]ps'), 'my-regexps')
                        zc.buildout.testing.normalize_path,
                        ]),
                ),
            ))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
