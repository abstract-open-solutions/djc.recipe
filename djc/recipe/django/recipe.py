# -*- coding: utf-8 -*-
"""This is able to set up a django system. It does not do much, besides setting
up a proper ``settings.py`` file and having a ``bin/django`` script load it.

The settings file uses a template (overridable) to be generated, making the
extension of this buildout to support grown up projects like Django and Pinax a
mere templating matter.

The settings file is saved in ``parts/name/settings.py``.
"""

import os, logging, random, shutil, imp, sys, collections
import zc.recipe.egg
from tempita import Template


def dotted_import(dotted_name, ws, extra_paths = []):
    """Tries to load a dotted name
    """
    paths = [ dist.location for dist in ws ]
    paths.extend(extra_paths)
    components = collections.deque(dotted_name.split('.'))
    paths = sys.path + paths
    load = True
    mod = None
    while len(components) > 0:
        component = components.popleft()
        if load:
            try:
                p, f, d = imp.find_module(component, paths)
            except ValueError:
                raise ImportError(dotted_name)
            mod = imp.load_module(component, p, f, d)
            try:
                paths = mod.__path__
            except AttributeError:
                load = False
        else:
            mod = getattr(mod, component)
    return mod


class _MemoizedProperty(object):
    """A getter that caches the response
    """

    def __init__(self, orig_callable):
        self._orig_callable = orig_callable

    def __get__(self, instance, owner):
        if instance is None:
            return None
        annotation = "_mp_%s" % self._orig_callable.__name__
        if not hasattr(instance, annotation):
            setattr(instance, annotation, self._orig_callable(instance))
        return getattr(instance, annotation)


def memoized_property(method):
    return _MemoizedProperty(method)


def normalize_keys(mapping):
    for k, v in mapping.items():
        yield (k.replace('-', '_'), v)


class Recipe(object):
    """A Django buildout recipe
    """

    def __init__(self, buildout, name, options):
        self.buildout, self.name, self.options = buildout, name, options
        self._logger = logging.getLogger(name)
        self.egg = zc.recipe.egg.Egg(
            self.buildout, self.options['recipe'], self.options
        )
        self.options['location'] = os.path.join(
            self.buildout['buildout']['parts-directory'], self.name
        )
        self.options.setdefault('extra-paths', '')
        self.options.setdefault('media-directory', 'static')
        if not ('urlconf' in self.options and 'templates' in self.options):
            if not 'project' in self.options:
                raise zc.buildout.UserError(
                    "A 'project' egg must be specified in %s "
                    "(es 'project = my.django.project') "
                    "if 'urlconf' and 'templates' are not." % self.name
                )
        # functions that are used in templates
        def t_absolute_url(url):
            return os.path.join(
                self.buildout['buildout']['directory'], url
            )
        
        # here go functions you'd like to have available in templates
        self._namespace_additions = {
            'absolute_url': t_absolute_url,
            'listify': lambda x: x.split()
        }

    @memoized_property
    def extra_paths(self):
        extra_paths = [
            self.options['location'],
            self.buildout['buildout']['directory']
        ]

        # Add libraries found by a site .pth files to our extra-paths.
        if 'pth-files' in self.options:
            import site
            for pth_file in self.options['pth-files'].splitlines():
                pth_libs = site.addsitedir(pth_file, set())
                if not pth_libs:
                    self._logger.warning(
                        "No site *.pth libraries found for pth_file=%s" % (
                            pth_file,
                        )
                    )
                else:
                    self._logger.info("Adding *.pth libraries=%s" % pth_libs)
                    self.options['extra-paths'] += '\n' + '\n'.join(pth_libs)

        pythonpath = [
            p.replace('/', os.path.sep) for p in
                self.options['extra-paths'].splitlines() if p.strip()
        ]

        extra_paths.extend(pythonpath)
        return extra_paths

    @memoized_property
    def secret(self):
        secret_file = os.path.join(
            self.buildout['buildout']['directory'],
            '.secret.cfg'
        )
        if os.path.isfile(secret_file):
            stream = open(secret_file, 'rb')
            data = stream.read().decode('utf-8').strip()
            stream.close()
            self._logger.debug("Read secret: %s" % data)
        else:
            stream = open(secret_file, 'wb')
            chars = u'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)'
            data = u''.join([random.choice(chars) for i in range(50)])
            stream.write(data.encode('utf-8')+u"\n")
            stream.close()
            self._logger.debug(
                "Generated secret: %s (and written to %s)" % (data, secret_file)
            )
        return data

    @memoized_property
    def settings_py(self):
        if 'settings-template' in self.options:
            template_fname = self.options['settings-template']
        else:
            template_fname = os.path.join(
                os.path.dirname(__file__),
                'settings.py.in'
            )
        self._logger.debug(
            "Loading settings template from %s" % template_fname
        )
        stream = open(template_fname, 'rb')
        template_definition = stream.read().decode('utf-8')
        stream.close()
        self._logger.info("Generating settings")
        namespace = dict(normalize_keys(self.options))
        namespace.update(self._namespace_additions)
        namespace.update({ 'name': self.name, 'secret': self.secret })
        template = Template(template_definition, namespace=namespace)
        return unicode(template)

    def create_script(self):
        eggs = ['djc.recipe.django']
        if 'project' in self.options:
            eggs.append(self.options['project'])
        requirements, ws = self.egg.working_set(eggs)
        self._logger.info("Creating script at %s" % self.options['executable'])
        return zc.buildout.easy_install.scripts(
            [(
                self.options.get('control-script', self.name),
                'djc.recipe.django.manage',
                'main'
            )],
            ws, self.options['executable'],
            self.options['bin-directory'],
            extra_paths = self.extra_paths,
            arguments = "'%s.settings'" % self.name
        )

    def install_project(self):
        if 'project' in self.options:
            try:
                requirements, ws = self.egg.working_set(
                    ['djc.recipe.django', self.options['project']]
                )
                project = dotted_import(self.options['project'], ws)
            except ImportError:
                self._logger.info(
                    "Specified project '%s' not found, attempting install" % (
                        self.options['project'],
                    )
                )
                requirements, ws = self.working_set
                buildout = self.buildout['buildout']
                if 'versions' in buildout and buildout['versions'] in self.buildout:
                    versions = self.buildout[buildout['versions']]
                else:
                    versions = None
                zc.buildout.easy_install.install(
                    [self.options['project']], buildout['eggs-directory'],
                    links = buildout.get('find-links', '').split(),
                    index = buildout.get('index'),
                    path = [
                        buildout['develop-eggs-directory'],
                        buildout['eggs-directory']
                    ],
                    always_unzip=True,
                    newest = self.buildout.newest,
                    allow_hosts = self.buildout._allow_hosts,
                    versions = versions,
                    working_set = ws
                )
                requirements, ws = self.egg.working_set(
                    ['djc.recipe.django', self.options['project']]
                )
                project = dotted_import(
                    self.options['project'],
                    ws
                )
            self.options.setdefault(
                'urlconf',
                '%s.urls' % self.options['project']
            )
            self.options.setdefault(
                'templates',
                os.path.join(os.path.dirname(project.__file__), 'templates')
            )

    def create_static(self):
        media_directory = os.path.join(
            self.buildout['buildout']['directory'],
            self.options['media-directory']
        )
        if os.path.exists(media_directory):
            self._logger.info(
                "Media directory %s exists, skipping" % media_directory
            )
            return [ media_directory ]
        if 'media-origin' in self.options:
            self._logger.info(
                "Copying media from '%s' to '%s'" % (
                    self.options['media-origin'],
                )
            )
            try:
                mod, directory = self.options['media-origin'].split(':')
            except ValueError:
                raise zc.buildout.UserError(
                    "Error in '%s': media_origin must be in the form "
                    "'custom.module:directory'" % self.name
                )
            try:
                mod = dotted_import(mod)
            except ImportError:
                raise zc.buildout.UserError(
                    "Error in '%s': media_origin is '%s' "
                    "but we cannot find module '%s'" % (
                        self.name, self.options['media-origin'], mod
                    )
                )
            orig_directory = os.path.join(
                os.path.dirname(mod.__file__),
                directory
            )
            if not os.path.isdir(orig_directory):
                raise zc.buildout.UserError(
                    "Error in '%s': media_origin is '%s' "
                    "but '%s' does not seem to be a directory" % (
                        self.name, self.options['media-origin'], directory
                    )
                )
            shutil.copytree(orig_directory, media_directory)
        else:
            self._logger.info(
                "Making empty media directory '%s'" % media_directory
            )
            os.makedirs(media_directory)
        return [ media_directory ]

    def create_project(self):
        project_dir = self.options['location']
        if not os.path.exists(project_dir):
            self._logger.debug("Creating %s" % project_dir)
            os.mkdir(project_dir)
        if not os.path.isdir(project_dir):
            raise zc.buildout.UserError(
                "Can't install %s: %s is not a directory!" % (
                    self.name, project_dir
                )
            )
        files = [
            { 'name': 'init.py', 'content': u'#\n' },
            { 'name': 'settings.py', 'content': self.settings_py }
        ]
        self._logger.info("Generating files in %s" % self.name)
        for f in files:
            fullpath = os.path.join(project_dir, f['name'])
            self._logger.debug("(Over)writing %s" % fullpath)
            st = open(fullpath, 'wb')
            st.write(f['content'].encode('utf-8'))
            st.close()
        return [ project_dir ]

    def install(self):
        """Installs the part"""
        generated = []
        self.install_project()
        return tuple(
            self.create_project() +
            self.create_static() +
            self.create_script()
        )

    update = install
