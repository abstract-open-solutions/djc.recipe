import os, shutil


class tree(dict):
    """A hashable, nested tree.

    This tree is substantially a nested dict, which is hashable and offers the
    ability to set (and get) nested trees within extra commands, ``mset`` and
    ``mget``.

    It also offers the ability to obtains all the subtrees, recursively, and
    their respective hashes and "paths", via the ``subtrees`` method.

    Let's start by looking at the hashing. The trees are hashable such as, if
    their keys and values are equal, their hash is the same (which is very good
    if you want to implement equality)::

        >>> from djc.recipe.copier import tree
        >>> a = tree([('a', 1), ('b', 2)])
        >>> b = tree([('a', 1), ('b', 2)])
        >>> hash(a) == hash(b)
        True
        >>> c = tree([('a', 1), ('b', 3)])
        >>> d = tree([('a', 1), ('c', 2)])
        >>> hash(a) == hash(c)
        False
        >>> hash(a) == hash(d)
        False

    This behavior is maintained even if we deal with nested trees, the same
    exact algorithm is propagated::

        >>> e = tree([('a', 1), ('b', a)])
        >>> f = tree([('a', 1), ('b', a)])
        >>> hash(e) == hash(f)
        True
        >>> g = tree([('a', 1), ('b', c)])
        >>> h = tree([('a', 1), ('b', d)])
        >>> hash(e) == hash(g)
        False
        >>> hash(e) == hash(h)
        False

    As we mentioned before, is is possible to do a "multi set" with just one
    command: if you want to put a value inside multiple nested trees, you can
    use a command that will create the "intermediate trees" for you if they are
    missing, and it's also possible to get the values the same way, avoiding
    the painful need to type dozens of square parenthesis::

        >>> t = tree()
        >>> t['a'] = 1
        >>> t['a']
        1
        >>> t.mset(['b', 'c', 'd'], 1)
        >>> t.mget(['b', 'c', 'd'])
        1

    However, if you try to use this method to get a non existing value (meaning
    there are no subtrees leading there), ``KeyError`` is raised::

        >>> t.mget(['a', 'b']) #doctest: +ELLIPSIS, +NORMALIZE_WHITESPACE
        Traceback (most recent call last):
          ...
        KeyError: ['a', 'b']

    If you try to set a value that implies the creation of an intermediate tree
    where a value is present (in this example, the ``a`` key holds a value, and
    each key can hold either a value or a subtree, not both), it is
    overwritten::

        >>> t.mset(['a', 'b'], 1)
        >>> isinstance(t['a'], tree)
        True
        >>> t.mget(['a', 'b'])
        1

    If you pass to ``mget`` or ``mset`` a key that is not a list or tuple, or
    that is "empty", ``ValueError`` is raised::

        >>> t.mset([], 1) # doctest: +ELLIPSIS, +NORMALIZE_WHITESPACE
        Traceback (most recent call last):
          ...
        ValueError: []
        >>> t.mget([]) # doctest: +ELLIPSIS, +NORMALIZE_WHITESPACE
        Traceback (most recent call last):
          ...
        ValueError: []
        >>> t.mset('foo', 1) # doctest: +ELLIPSIS, +NORMALIZE_WHITESPACE
        Traceback (most recent call last):
          ...
        ValueError: foo
        >>> t.mget('foo') # doctest: +ELLIPSIS, +NORMALIZE_WHITESPACE
        Traceback (most recent call last):
          ...
        ValueError: foo

    Last but not least, you can obtain the hashes of all subtrees by calling
    the ``subtrees`` method. This method accepts a single parameter which is
    the separator that is used to join keys in order to compose the subtree's
    "path".

    The return value is a list of tuples in the form (path, hash)::

        >>> [ i for i in t.subtrees('/') ] #doctest: +NORMALIZE_WHITESPACE
        [('a', -8073526862451315244), ('b', 5384660820297694132),
         ('b/c', -5082000491912973890)]

    """

    def mset(self, key, value):
        """Sets a value located in a subtree, creating intermediate subtrees.
        """
        if not isinstance(key, (list, tuple)) or len(key) <= 0:
            raise ValueError(key)
        current = self
        for item in key[:-1]:
            if item not in current or not isinstance(current[item], tree):
                current[item] = tree()
            current = current[item]
        current[key[-1]] = value

    def mget(self, key):
        """Gets a value located in a subtree.
        """
        if not isinstance(key, (list, tuple)) or len(key) <= 0:
            raise ValueError(key)
        current = self
        for item in key[:-1]:
            current = current[item]
            if not isinstance(current, tree):
                raise KeyError(key)
        return current[key[-1]]

    def __hash__(self):
        return hash(tuple(sorted(self.items())))

    def subtrees(self, joiner):
        """Returns the subtrees and their hashes.
        """
        for key, element in self.iteritems():
            if isinstance(element, tree):
                yield (key, hash(element))
                for subkey, subhash in element.subtrees(joiner):
                    yield (joiner.join([key, subkey]), subhash)


class Copier(object):
    """An object that allows to copy multiple sources into one target, merging
    the results where possible.

    It takes a single initialization parameter, a boolean ``link`` that, if
    true, will symlink files (or directories) instead of copying them.

    We will start with a source directory that looks like this::

        source
          one
            a
              c.txt
            b.txt
            c
              d.txt
              e.txt
          two
            a
              b.txt
          three
            a
              a.txt
              d.txt
          zza
            zza.txt
          zzb
            zzb.txt
            zzc
              zzc.txt
            zzd
              zzd.txt
          zzz
            zzz.txt

    And will be configured to copy things to a target directory that will,
    after the copy, look like this::

        target
          a
            b.txt
            c.txt
          b.txt
          c
            d.txt
            e.txt
          three
            a
              c.txt
              d.txt
          zza.txt
          zzb
            zzb.txt
            zzc
              zzc.txt
            zzd
              zzd.txt
          zzz
            zzz.txt

    In order to do this, we instantiate our copier (``link`` is false else the
    tests will break under windows)::

        >>> import os
        >>> copier = Copier(link=False)

    And then use the ``copy`` method to copy ``one`` and ``two`` into the root
    target directory, and ``three`` into the ``three`` subdirectory within the
    target::

        >>> copier.copy(os.path.join(source, 'one'), target)
        >>> copier.copy(os.path.join(source, 'two'), target)
        >>> copier.copy(
        ...     os.path.join(source, 'three'),
        ...     os.path.join(target, 'three')
        ... )
        >>> copier.copy(os.path.join(source, 'zza'), target)
        >>> copier.copy(os.path.join(source, 'zzb'), target)
        >>> copier.copy(os.path.join(source, 'zzz'), target)


    .. note::
       The following is totally not necessary in normal usage. We do it here
       for mere testing purposes

    The next thing we do is call the ``merge`` method and inspect which
    operations the system will perform: the operations are threeple in the form
    (type, source, target), where type is "tree" for directories and "single"
    for single files. We will see that the system is smart enough not to copy
    the files inside subtrees that remain the same, but copy those subtrees
    over in a single operation::

        >>> copier.operations #doctest: +ELLIPSIS, +NORMALIZE_WHITESPACE
        [('single', '.../one/b.txt', '.../b.txt'),
         ('single', '.../one/a/c.txt', '.../a/c.txt'),
         ('single', '.../one/c/e.txt', '.../c/e.txt'),
         ('single', '.../one/c/d.txt', '.../c/d.txt'),
         ('single', '.../two/a/b.txt', '.../a/b.txt'),
         ('single', '.../three/a/a.txt', '.../three/a/a.txt'),
         ('single', '.../three/a/d.txt', '.../three/a/d.txt'),
         ('single', '.../zza/zza.txt', '.../zza.txt'),
         ('single', '.../zzb/zzb.txt', '.../zzb/zzb.txt'),
         ('single', '.../zzb/zzc/zzc.txt', '.../zzb/zzc/zzc.txt'),
         ('single', '.../zzb/zzd/zzd.txt', '.../zzb/zzd/zzd.txt'),
         ('single', '.../zzz/zzz/zzz.txt', '.../zzz/zzz.txt')]
        >>> copier._merge()
        >>> copier.operations #doctest: +ELLIPSIS, +NORMALIZE_WHITESPACE
        [('tree', '.../one/c', '.../c'),
         ('tree', '.../three/a', '.../three/a'),
         ('tree', '.../zzb', '.../zzb'),
         ('tree', '.../zzz', '.../zzz'),
         ('single', '.../one/a/c.txt', '.../a/c.txt'),
         ('single', '.../one/b.txt', '.../b.txt'),
         ('single', '.../two/a/b.txt', '.../a/b.txt'),
         ('single', '.../zza/zza.txt', '.../zza.txt')]

    If we then call ``execute`` to actually perform the copy, we see that the
    target respect the tree model that we gave above::

        >>> copier.execute()
        >>> ls(target)
        d  a
        -  b.txt
        d  c
        d  three
        -  zza.txt
        d  zzb
        d  zzz
        >>> ls(target, 'a')
        -  b.txt
        -  c.txt
        >>> ls(target, 'c')
        -  d.txt
        -  e.txt
        >>> ls(target, 'three')
        d  a
        >>> ls(target, 'three', 'a')
        -  a.txt
        -  d.txt
        >>> ls(target, 'zzb')
        -  zzb.txt
        d  zzc
        d  zzd
        >>> ls(target, 'zzb', 'zzc')
        -  zzc.txt
        >>> ls(target, 'zzb', 'zzd')
        -  zzd.txt
        >>> ls(target, 'zzz')
        -  zzz.txt

    Had we passed ``link`` as true, it would have linked entire subdirectories
    where possible.
    """

    def __init__(self, link=False):
        self.link = link
        self.origins = tree()
        self.targets = tree()
        self.target_bases = []
        self.operations = []
        self.merged = False

    def copy(self, origin, target):
        """Schedules a copy from ``origin`` to ``target``.
        """
        for root, __, files in os.walk(origin):
            for file_ in files:
                file_origin = os.path.join(root, file_)
                file_target = os.path.join(
                    target,
                    file_origin[len(origin):].lstrip(os.sep)
                )
                self.origins.mset(
                    file_origin.split(os.sep),
                    origin
                )
                self.targets.mset(
                    file_target.split(os.sep),
                    origin
                )
                self.operations.append(('single', file_origin, file_target))
                self.target_bases.append(target)

    def is_valid(self, target):
        for target_base in self.target_bases:
            if target_base.startswith(target):
                return False
        return True

    def _merge(self): # pylint: disable=R0912
        """Merges the operations that can be done "in bulk", because the
        subtrees are invariant.
        """
        origin_trees = self.origins.subtrees(os.sep)
        target_trees = {}
        tree_operations = []
        for path, hash_ in self.targets.subtrees(os.sep):
            target_trees[hash_] = path
        for path, hash_ in origin_trees:
            if hash_ in target_trees and self.is_valid(target_trees[hash_]):
                tree_operations.append(('tree', path, target_trees[hash_]))
        if len(tree_operations) > 0:
            tree_operations.sort(key=lambda x: x[1])
            reduced_tree_operations = []
            for operation in tree_operations:
                if len(reduced_tree_operations) > 0:
                    base_operation = reduced_tree_operations[-1]
                    if not operation[1].startswith(base_operation[1]):
                        reduced_tree_operations.append(operation)
                else:
                    reduced_tree_operations.append(operation)
            tree_operations = reduced_tree_operations
            self.operations.sort(key=lambda x: x[1])
            new_operations = [ o for o in tree_operations ]
            operation_match = False
            for operation in self.operations:
                if len(tree_operations) > 0:
                    if operation[1].startswith(tree_operations[0][1]):
                        operation_match = True
                    else:
                        if operation_match:
                            tree_operations.pop(0)
                            if len(tree_operations) > 0 and \
                                    operation[1].startswith(
                                        tree_operations[0][1]):
                                operation_match = True
                            else:
                                operation_match = False
                        if not operation_match:
                            new_operations.append(operation)
            self.operations = new_operations
        self.merged = True

    def execute(self):
        """Executes the scheduled copies.
        """
        if not self.merged:
            self._merge()
        for type_, source, target in self.operations:
            dirname = os.path.dirname(target.rstrip(os.sep))
            if os.path.exists(dirname) and os.path.isfile(dirname):
                os.remove(dirname)
            if not os.path.exists(dirname):
                os.makedirs(dirname)
            if os.path.exists(target):
                if type_ == 'tree' and not os.path.islink(target):
                    shutil.rmtree(target)
                else:
                    os.remove(target)
            if self.link and hasattr(os, 'symlink'):
                os.symlink(source, target)
            else:
                if type_ == 'tree':
                    shutil.copytree(source, target)
                else:
                    shutil.copy(source, target)
