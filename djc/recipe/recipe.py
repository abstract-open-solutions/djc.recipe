# -*- coding: utf-8 -*-
"""This is able to set up a django system. It does not do much, besides setting
up a proper ``settings.py`` file and having a ``bin/django`` script load it.

The settings file uses a template (overridable) to be generated, making the
extension of this buildout to support grown up projects like Django and Pinax a
mere templating matter.

The settings file is saved in ``parts/name/settings.py``.
"""

import os, re, logging, random, sys, pprint
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

def app_factory(global_config, **local_config):
    """This function wraps our simple WSGI app so it
    can be used with paste.deploy"""
    return application
'''


def touch(path, content = ''):
    if os.path.isfile(path):
        fp = open(path, 'wb')
    else:
        fp = open(path, 'ab')
        content = ''
    fp.write(content)
    fp.close()


def get_destination(fullpath, origin, destination):
    components = [ destination ] + fullpath[len(origin):].split(os.sep)
    return os.path.join(*components)


def copytree(origin, destination, logger):
    if not os.path.isdir(destination):
        logger.debug("Creating missing destination %s" % destination)
        os.makedirs(destination)
    for root, dirs, files in os.walk(origin):
        for name in files:
            origin_path = os.path.join(root, name)
            destination_path = get_destination(
                origin_path, origin, destination
            )
            logger.debug(
                "Copying %s to %s" % (origin_path, destination_path)
            )
            origin_fp = open(origin_path, "rb")
            destination_fp = open(destination_path, "wb")
            destination_fp.write(origin_fp.read())
            origin_fp.close()
            destination_fp.close()
        for name in dirs:
            origin_path = os.path.join(root, name)
            destination_path = get_destination(
                origin_path, origin, destination
            )
            if not os.path.isdir(destination_path):
                logger.debug(
                    "Making intermediate directory %s" % destination_path
                )
                os.mkdir(destination_path)


def dotted_import(module, paths):
    old_syspath = sys.path
    sys.path = list(set(sys.path) | set(paths))
    components = module.split('.')
    mod = None
    try:
        mod = __import__(module)
    except ImportError:
        i = 1
        for i in xrange(1, len(components)):
            try:
                mod = __import__(".".join(components[:-1*i]))
            except ImportError:
                pass
            else:
                break
        components = components[i:]
    if mod is None:
        raise ImportError("Could not import %s" % module)
    if module != mod.__name__:
        for submod in module[len(mod.__name__)+1:].split('.'):
            try:
                mod = getattr(mod, submod)
            except AttributeError:
                mod = __import__("%s.%s" % (mod.__name__, submod))
    sys.path = old_syspath
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
        
        self.options.setdefault('static-directory', 'static')
        self.options.setdefault('static-url', 'static')
        self.options.setdefault('media-directory', 'media')
        self.options.setdefault('media-url', 'media')
        self.options.setdefault('admin-media', 'admin_media')
        for option in ('static-url', 'media-url', 'admin-media'):
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

        self.options.setdefault('middleware', '')
        self.options.setdefault('apps', '')
        self.options.setdefault('template-loaders', '')
        self.options.setdefault('template-context-processors', '')
        self.options.setdefault('authentication-backends', '')

        self.options.setdefault('debug', 'false')
        self.options.setdefault('internal-ips', '127.0.0.1')

        self.options.setdefault('fixture-dirs', '')

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
            template_definition += u"\n\n# Extension template %s\n\n" % (
                self.options['settings-template-extension'],
            )
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

    def _create_script(self, name, path, module, attr, extra_attr = []):
        requirements, ws = self.egg.working_set(self.eggs)
        self._logger.info(
            "Creating script at %s" % (os.path.join(path, name),)
        )
        if len(extra_attr) > 0:
            extras = ", " + ", ".join(extra_attr)
        else:
            extras = ''
        return zc.buildout.easy_install.scripts(
            [(name, module, attr)],
            ws, self.options['executable'],
            path,
            extra_paths = self.extra_paths,
            arguments = "'%s'%s" % (
                os.path.join(
                    self.options['location'],
                    _settings_name
                ),
                extras
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
        # uwsgi needs a module in the pythonpath to load it out, so we satisfy
        # uwsgi's pressing needs
        module_path = os.path.join(
            self.options['location'],
            'djc_recipe_%s' % self.name
        )
        if not os.path.isdir(module_path):
            os.mkdir(module_path)
        touch(os.path.join(module_path, '__init__.py'), content = '#')
        extras = []
        if 'wsgi-logfile' in self.options:
            extras.append(
                "logfile = '%s'" % os.path.join(
                    self.buildout['buildout']['directory'],
                    self.options['wsgi-logfile']
                )
            )
        script = self._create_script(
            'app.py',
            module_path,
            'djc.recipe.wsgi',
            'main',
            extras
        )
        zc.buildout.easy_install.script_template = _script_template
        return script

    def install_project(self):
        if 'project' in self.options:
            try:
                requirements, ws = self.egg.working_set(self.eggs)
                project = dotted_import(
                    self.options['project'],
                    [d.location for d in ws]
                )
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
                    [d.location for d in ws]
                )
            self.options.setdefault(
                'urlconf',
                '%s.urls' % self.options['project']
            )
            self.options.setdefault(
                'templates',
                os.path.join(os.path.dirname(project.__file__), 'templates')
            )

    def copy_origin(self, origin, destination):
        self._logger.info(
            "Copying media from '%s' to '%s'" % (origin, destination)
        )
        try:
            components = origin.split(':')
            mod, directory = components[:2]
        except ValueError:
            raise zc.buildout.UserError(
                "Error in '%s': media_origin must be in the form "
                "'custom.module:directory'" % self.name
            )
        try:
            requirements, ws = self.egg.working_set(self.eggs)
            mod = dotted_import(mod, [d.location for d in ws])
        except ImportError:
            raise zc.buildout.UserError(
                "Error in '%s': media_origin is '%s' "
                "but we cannot find module '%s'" % (self.name, origin, mod)
            )
        orig_directory = os.path.join(
            os.path.dirname(mod.__file__),
            directory
        )
        if not os.path.isdir(orig_directory):
            raise zc.buildout.UserError(
                "Error in '%s': media_origin is '%s' "
                "but '%s' does not seem to be a directory" % (
                    self.name, origin, directory
                )
            )
        if len(components) > 2:
            copytree(
                orig_directory,
                os.path.join(destination, components[2]),
                self._logger
            )
        else:
            copytree(orig_directory, destination, self._logger)

    def create_static(self, prefix):
        media_directory = os.path.join(
            self.buildout['buildout']['directory'],
            self.options['%s-directory' % prefix]
        )
        origin_option = '%s-origin' % prefix
        if origin_option in self.options:
            if not os.path.isdir(media_directory):
                self._logger.info(
                    "Making media directory '%s'" % media_directory
                )
                os.makedirs(media_directory)
            for origin in self.options[origin_option].split():
                self.copy_origin(origin, media_directory)
        else:
            if not os.path.isdir(media_directory):
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
            self.create_static('static') + 
            self.create_static('media') + 
            self.create_script()
        )
        if self._template_namespace['boolify'](self.options.get('wsgi', 'false')):
            files += self.create_wsgi_script()
        return tuple(files)

    update = install
