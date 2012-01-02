import unittest, doctest, tempfile, shutil, os
from zc.buildout.testing import ls, cat
from djc.recipe import copier


def create_file(base, path):
    name, __ = os.path.splitext(path[-1])
    dir_path = os.path.join(base, os.path.join(*path[:-1]))
    if not os.path.isdir(dir_path):
        os.makedirs(dir_path)
    with open(os.path.join(dir_path, path[-1]), 'wb') as f:
        f.write("%s\n" % name)


def setUp(test):
    test.globs['ls'] = ls
    test.globs['cat'] = cat
    test.globs['source'] = tempfile.mkdtemp(suffix='source',
                                            prefix='tmp-tests-djc.recipe')
    test.globs['target'] = tempfile.mkdtemp(suffix='target',
                                            prefix='tmp-tests-djc.recipe')
    create_file(test.globs['source'], ['one', 'a', 'c.txt'])
    create_file(test.globs['source'], ['one', 'b.txt'])
    create_file(test.globs['source'], ['one', 'c', 'd.txt'])
    create_file(test.globs['source'], ['one', 'c', 'e.txt'])
    create_file(test.globs['source'], ['two', 'a', 'b.txt'])
    create_file(test.globs['source'], ['three', 'a', 'a.txt'])
    create_file(test.globs['source'], ['three', 'a', 'd.txt'])
    create_file(test.globs['source'], ['zza', 'zza.txt'])
    create_file(test.globs['source'], ['zzb', 'zzb', 'zzb.txt'])
    create_file(test.globs['source'], ['zzb', 'zzb', 'zzc', 'zzc.txt'])
    create_file(test.globs['source'], ['zzb', 'zzb', 'zzd', 'zzd.txt'])
    create_file(test.globs['source'], ['zzz', 'zzz', 'zzz.txt'])


def tearDown(test):
    shutil.rmtree(test.globs['source'], ignore_errors=True)
    shutil.rmtree(test.globs['target'], ignore_errors=True)


def test_suite():
    suite = unittest.TestSuite(
        [
            doctest.DocTestSuite(
                copier,
                setUp=setUp,
                tearDown=tearDown
            )
        ]
    )
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
