# -*- coding: utf-8 -*-
"""This is able to set up a django system. It does not do much, besides setting
up a proper ``settings.py`` file and having a ``bin/django`` script load it.

The settings file uses a template (overridable) to be generated, making the
extension of this buildout to support grown up projects like Django and Pinax a
mere templating matter.

The settings file is saved in ``parts/name/settings.py``.
"""

import os, re, logging, random, shutil, imp, sys, collections, pprint
import zc.recipe.egg
from tempita import Template


_egg_name = 'djc.recipe'
_settings_name = 'settings.py'

_wsgi_script_template = '''

%(relative_paths_setup)s
import sys
sys.path[0:0] = [
  %(path)s,
  ]
%(initialization)s
import %(module_name)s

application = %(module_name)s.%(attrs)s(%(arguments)s)
'''


def dotted_import(dotted_name, ws, extra_paths = []):
    """Tries to load a dotted name
    """
    paths = [ dist.location for dist in ws ]
    paths.extend(extra_paths)
    components = collections.deque(dotted_name.split('.'))
    paths = sys.path + paths
    load = True
    mod = None
    try:
        imp.acquire_lock()
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
    except Exception:
        imp.release_lock()
        raise
    imp.release_lock()
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

        self.options.setdefault('site-id', '')
        self.options.setdefault('site-domain', '')
        self.options.setdefault('site-name', '')
        
        self.options.setdefault('media-directory', 'static')
        self.options.setdefault('media-url', 'media')
        self.options.setdefault('admin-media', 'admin_media')
        for option in ('media-url', 'admin-media'):
            self.options[option] = self.options[option].strip('/')
        
        self.options.setdefault('database-engine', 'sqlite3')
        self.options.setdefault('database-name', 'storage.db')
        self.options.setdefault('database-user', '')
        self.options.setdefault('database-password', '')
        self.options.setdefault('database-host', '')
        self.options.setdefault('database-port', '')

        self.options.setdefault('smtp-host', 'localhost')
        self.options.setdefault('smtp-port', '25')
        self.options.setdefault('smtp-user', '')
        self.options.setdefault('smtp-password', '')
        self.options.setdefault('smtp-tls', 'false')

        self.options.setdefault('cache-backend', 'locmem:///')
        self.options.setdefault('cache-timeout', '60*5')
        self.options.setdefault('cache-prefix', 'Z')
        
        self.options.setdefault('timezone', 'America/Chicago')
        self.options.setdefault('language-code', 'en-us')
        self.options.setdefault('languages', '')

        self.options.setdefault('admins', "John Smith <root@localhost>")
        self.options.setdefault('managers', 'ADMINS')

        self.options.setdefault('base-settings', '')

        _middleware_default = '''
            django.middleware.common.CommonMiddleware
            django.contrib.sessions.middleware.SessionMiddleware
            django.contrib.auth.middleware.AuthenticationMiddleware
            django.middleware.doc.XViewMiddleware
        '''

        _apps_default = '''
            django.contrib.auth
            django.contrib.contenttypes
            django.contrib.sessions
            django.contrib.admin
        '''

        _template_loaders_default = '''
            django.template.loaders.filesystem.load_template_source
            django.template.loaders.app_directories.load_template_source
        '''

        if self.options['base-settings']:
            _middleware_default = ''
            _apps_default = ''
            _template_loaders_default = ''

        self.options.setdefault('middleware', _middleware_default)
        self.options.setdefault('apps', _apps_default)
        self.options.setdefault('template-loaders', _template_loaders_default)
        self.options.setdefault('template-context-processors', '')
        self.options.setdefault('authentication-backends', '')

        self.options.setdefault('debug', 'false')

        self.eggs = [ _egg_name ]
        if 'eggs' in self.buildout['buildout']:
            self.eggs.extend(self.buildout['buildout']['eggs'].split())
        if 'eggs' in self.options:
            self.eggs.extend(self.options['eggs'].split())

        if not ('urlconf' in self.options and 'templates' in self.options):
            if not 'project' in self.options:
                raise zc.buildout.UserError(
                    "A 'project' egg must be specified in %s "
                    "(es 'project = my.django.project') "
                    "if 'urlconf' and 'templates' are not." % self.name
                )
        # functions that are used in templates
        def t_absolute_path(url):
            return os.path.join(
                self.buildout['buildout']['directory'], url
            )

        def t_listify(data):
            lines = []
            for raw_line in data.splitlines():
                line = raw_line.strip()
                if line != '':
                    lines.append(line)
            return lines

        def t_rfc822tuplize(data):
            m = re.match('(.+)\s+<(.+)>', data)
            if m is None:
                return (data,)
            else:
                return (m.group(1), m.group(2))

        def t_boolify(data):
            if data.lower() in ['true', 'on', '1']:
                return True
            return False

        def t_join(data, infix, prefix="", suffix=""):
            return prefix+infix.join(data)+suffix
        
        # here go functions you'd like to have available in templates
        self._template_namespace = {
            'absolute_path': t_absolute_path,
            'listify': t_listify,
            'rfc822tuplize': t_rfc822tuplize,
            'boolify': t_boolify,
            'join': t_join
        }

    @memoized_property
    def extra_paths(self):
        extra_paths = []
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
        if 'settings-template-extension' in self.options:
            self._logger.debug(
                "Loading settings extension template from %s" % (
                    self.options['settings-template-extension'],
                )
            )
            stream = open(
                self.options['settings-template-extension'],
                'rb'
            )
            template_definition += u"\n\n# Extension template %s\n\n"
            template_definition += stream.read().decode('utf-8')
            stream.close()

        variables = dict(normalize_keys(self.options))
        variables.update({ 'name': self.name, 'secret': self.secret })
        self._logger.debug(
            "Variable computation terminated:\n%s" % pprint.pformat(variables)
        )
        template = Template(
            template_definition,
            namespace=self._template_namespace
        )
        self._logger.debug(
            "Interpolating template, namespace is:\n%s" % pprint.pformat(
                self._template_namespace
            )
        )
        return template.substitute(variables)

    def _create_script(self, name, path, module, attr):
        requirements, ws = self.egg.working_set(self.eggs)
        self._logger.info(
            "Creating script at %s" % (os.path.join(path, name),)
        )
        return zc.buildout.easy_install.scripts(
            [(name, module, attr)],
            ws, self.options['executable'],
            path,
            extra_paths = self.extra_paths,
            arguments = "'%s'" % os.path.join(
                self.options['location'],
                _settings_name
            )
        )

    def create_script(self):
        return self._create_script(
            self.options.get('control-script', self.name),
            self.buildout['buildout']['bin-directory'],
            'djc.recipe.manage',
            'main'
        )

    def create_wsgi_script(self):
        _script_template = zc.buildout.easy_install.script_template
        zc.buildout.easy_install.script_template = \
                zc.buildout.easy_install.script_header + \
                    _wsgi_script_template
        script = self._create_script(
            '%s.wsgi.py' % self.name,
            self.options['location'],
            'djc.recipe.wsgi',
            'main'
        )
        zc.buildout.easy_install.script_template = _script_template
        return script

    def install_project(self):
        if 'project' in self.options:
            try:
                requirements, ws = self.egg.working_set(self.eggs)
                project = dotted_import(self.options['project'], ws)
            except ImportError:
                self._logger.info(
                    "Specified project '%s' not found, attempting install" % (
                        self.options['project'],
                    )
                )
                requirements, ws = self.egg.working_set(self.eggs)
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
                egg = zc.recipe.egg.Egg(
                    self.buildout, self.options['project'], self.options
                )
                requirements, ws = egg.working_set([ self.options['project'] ])
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
                    media_directory
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
                requirements, ws = self.egg.working_set(self.eggs)
                mod = dotted_import(mod, ws)
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
            os.makedirs(project_dir)
        if not os.path.isdir(project_dir):
            raise zc.buildout.UserError(
                "Can't install %s: %s is not a directory!" % (
                    self.name, project_dir
                )
            )
        self._logger.info("Generating settings in %s" % project_dir)
        fullpath = os.path.join(project_dir, _settings_name)
        self._logger.debug("(Over)writing %s" % fullpath)
        st = open(fullpath, 'wb')
        st.write(self.settings_py.encode('utf-8'))
        st.close()
        return [ project_dir ]

    def install(self):
        """Installs the part
        """
        
        self.install_project()
        files = (
            self.create_project() + 
            self.create_static() + 
            self.create_script()
        )
        if self._template_namespace['boolify'](self.options.get('wsgi', 'false')):
            files += self.create_wsgi_script()
        return tuple(files)

    update = install
