# -*- coding: utf-8 -*-
"""
Doctest runner for 'djc.recipe'.
"""
__docformat__ = 'restructuredtext'

import unittest, os, tempfile, shutil
import zc.buildout.tests
import zc.buildout.testing

from zope.testing import doctest, renormalizing

optionflags =  (doctest.ELLIPSIS |
                doctest.NORMALIZE_WHITESPACE |
                doctest.REPORT_ONLY_FIRST_FAILURE)

def setUp(test):
    normpath, join, dirname = os.path.normpath, os.path.join, os.path.dirname
    zc.buildout.testing.buildoutSetUp(test)
    zc.buildout.testing.install_develop('djc.recipe', test)
    src = join(test.globs['sample_buildout'], 'src')
    zc.buildout.testing.mkdir(src)
    for app in ['dummydjangoapp1', 'dummydjangoapp2']:
        shutil.copytree(
            normpath(join(dirname(__file__), '..', 'testing', 'src', app)),
            join(src, app)
        )
    try:
        tmpdir = tempfile.mkdtemp(prefix='djc.recipe.tests')
        shutil.copytree(
            normpath(
                join(
                    dirname(__file__), '..', 'testing', 'src', 'dummydjangoprj'
                )
            ),
            join(tmpdir, 'dummydjangoprj')
        )
        packages = join(test.globs['sample_buildout'], 'packages')
        zc.buildout.testing.mkdir(packages)
        zc.buildout.testing.sdist(
            join(tmpdir, 'dummydjangoprj'),
            packages
        )
    except:
        raise
    finally:
        shutil.rmtree(tmpdir)
    cache_dir = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            '..',
            '..',
            '..',
            'test-cache'
        )
    )
    if not os.path.isdir(cache_dir):
        os.makedirs(cache_dir)
    test.globs['cache_dir'] = cache_dir


def test_suite():
    suite = unittest.TestSuite((
            doctest.DocFileSuite(
                '../README.rst',
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
