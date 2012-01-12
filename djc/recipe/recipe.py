# -*- coding: utf-8 -*-
# pylint: disable-msg=W0602,W0102,R0912,R0915
"""This is able to set up a django system. It does not do much, besides setting
up a proper ``settings.py`` file and having a ``bin/django`` script load it.

The settings file uses a template (overridable) to be generated, making the
extension of this buildout to support grown up projects like Django and Pinax a
mere templating matter.

The settings file is saved in ``parts/name/settings.py``.
"""

import os, re, logging, random, sys, pprint, urllib
import zc.recipe.egg
from tempita import Template, bunch
from copier import Copier


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


def dotted_import(module, paths):
    old_syspath = sys.path
    sys.path = list(set(sys.path) | set(paths))
    components = module.split('.')
    mod = None
    try:
        mod = __import__(module)
    except ImportError:
        for i in xrange(1, len(components)):
            try:
                mod = __import__(".".join(components[:-1*i]))
            except ImportError:
                pass
            else:
                break
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


# BBB: Due to backward compatibility reasons, we support an array of regexes
# that match db urls specifications.
#
# These are tried in order, so first the deprecated method is tried, then the
# new one is tried. An "unquote" function is also specified.
dburl_regexes = [
    (re.compile(
        r"(?P<ENGINE>[a-zA-Z0-9_.]+)://(?:"
        r"(?P<USER>[a-zA-Z0-9_./+\-]+):"
        r"(?P<PASSWORD>[a-zA-Z0-9_./+\-]+)@)?"
        r"(?P<HOST>[a-zA-Z0-9.]+)?"
        r"(?::(?P<PORT>[0-9]+))?/"
        r"(?P<NAME>[a-zA-Z0-9_./+\-]+)"
        r"(?:\((?P<OPTIONS>[a-zA-Z0-9_./=,+\-]+)\))?"
     ), urllib.unquote_plus),
    (re.compile(
        r"engine=(?P<ENGINE>\S+)\s+"
        r"(?:user=(?P<USER>\S+)\s+"
        r"password=(?P<PASSWORD>\S+)\s+)?"
        r"(?:host=(?P<HOST>\S+)\s+)?"
        r"(?:port=(?P<PORT>[0-9]+)\s+)?"
        r"name=(?P<NAME>[a-zA-Z0-9_./+\-]+)"
        r"(?:\s+options=\((?P<OPTIONS>\S+)\))?"
     ), lambda x: x)
]


def split_dburl(url):
    global dburl_regexes

    for regex, unquote in dburl_regexes:
        m = regex.match(url)
        if m is not None:
            result = m.groupdict()
            for key in result.keys():
                if result[key] is None:
                    del result[key]
            for key in ['USER', 'PASSWORD', 'NAME']:
                if key in result:
                    result[key] = unquote(result[key])
            if 'OPTIONS' in result:
                options = [ o.strip() for o in result['OPTIONS'].split(',') ]
                result['OPTIONS'] = {}
                for option in options:
                    try:
                        name, value = option.split('=')
                    except ValueError:
                        raise ValueError(
                            ("The database url '%s' is incorrect, "
                             "we cannot split the option '%s'") % (
                                url, option
                            )
                        )
                    result['OPTIONS'][unquote(name)] = unquote(value)
            return result
    # If we couldn't match any regex, this is invalid
    raise ValueError(
        "The database url '%s' is incorrect" % url
    )


class Recipe(object):
    """A Django buildout recipe
    """

    def __init__(self, buildout, name, options):
        self.buildout, self.name, self.options = buildout, name, options
        self._logger = logging.getLogger(name)

        self.options['location'] = os.path.join(
            self.buildout['buildout']['parts-directory'], self.name
        )
        self.options.setdefault('extra-paths', '')
        self.options.setdefault('coding', 'utf-8')

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

        self.options.setdefault('database-engine', '')
        self.options.setdefault('database-name', '')
        self.options.setdefault('database-user', '')
        self.options.setdefault('database-password', '')
        self.options.setdefault('database-host', '')
        self.options.setdefault('database-port', '')

        self.options.setdefault(
            'database',
            'engine=django.db.backends.sqlite3 name=%s' %  os.path.join(
                self.buildout['buildout']['directory'],
                'storage.db'
            )
        )
        self.options.setdefault('additional-databases', '')

        self.options.setdefault(
            'mail-backend',
            'django.core.mail.backends.smtp.EmailBackend'
        )
        self.options.setdefault('mail-filepath', '')
        self.options.setdefault('smtp-host', '')
        self.options.setdefault('smtp-port', '')
        self.options.setdefault('smtp-user', '')
        self.options.setdefault('smtp-password', '')
        self.options.setdefault('smtp-tls', 'false')

        self.options.setdefault('cache-backend', 'locmem:///')
        self.options.setdefault('cache-timeout', '60*5')
        self.options.setdefault('cache-prefix', 'Z')

        self.options.setdefault('timezone', 'America/Chicago')
        self.options.setdefault('language-code', 'en-us')
        self.options.setdefault('languages', '')

        self.options.setdefault('server-email', "root@localhost")
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

        self.options.setdefault('environment-vars', '')

        self.eggs = [ _egg_name ]
        if 'eggs' in self.buildout['buildout']:
            self.eggs.extend(self.buildout['buildout']['eggs'].split())
        if 'eggs' in self.options:
            self.eggs.extend(self.options['eggs'].split())
        if 'project' in self.options:
            self.eggs.append(self.options['project'])

        if not ('urlconf' in self.options and 'templates' in self.options):
            if not 'project' in self.options:
                raise zc.buildout.UserError(
                    "A 'project' egg must be specified in %s "
                    "(es 'project = my.django.project') "
                    "if 'urlconf' and 'templates' are not." % self.name
                )

        # We will create a fake python module into which all our generated
        # scripts and settings will live. This makes them importable
        self.module_path = os.path.join(
            self.options['location'],
            'djc_recipe_%s' % self.name
        )


        # here go functions you'd like to have available in templates
        self._template_namespace = {
            'absolute_path': self.t_absolute_path,
            'listify': self.t_listify,
            'rfc822tuplize': self.t_rfc822tuplize,
            'boolify': self.t_boolify,
            'join': self.t_join,
            'dump': repr
        }

    @staticmethod
    def t_listify(data):
        lines = []
        for raw_line in data.splitlines():
            line = raw_line.strip()
            if line != '':
                lines.append(line)
        return lines

    def t_absolute_path(self, url):
        return os.path.join(
            self.buildout['buildout']['directory'], url
        )

    @staticmethod
    def t_rfc822tuplize(data):
        m = re.match('(.+)\s+<(.+)>', data)
        if m is None:
            return (data,)
        else:
            return (m.group(1), m.group(2))

    @staticmethod
    def t_boolify(data):
        if data.lower() in ['true', 'on', '1']:
            return True
        return False

    @staticmethod
    def t_join(data, infix, prefix="", suffix=""):
        return prefix+infix.join(data)+suffix

    @memoized_property
    def rws(self):
        egg = zc.recipe.egg.Egg(
            self.buildout, self.options['recipe'], self.options
        )
        return egg.working_set(self.eggs)

    @memoized_property
    def extra_paths(self):
        extra_paths = [
            self.options['location']
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
            data = u''.join([random.choice(chars) for __ in range(50)])
            stream.write(data.encode('utf-8')+u"\n")
            stream.close()
            self._logger.debug(
                "Generated secret: %s (and written to %s)" % (data, secret_file)
            )
        return data

    def fix_databases(self, variables):
        databases = {}
        database = variables.pop('database').strip()
        if database != '':
            databases['default'] = split_dburl(database)
        for key in [ 'database_engine', 'database_name', 'database_user',
                          'database_password', 'database_host',
                          'database_port' ]:
            value = variables.pop(key).strip()
            if value != '':
                databases['default'][key[len('database_'):].upper()] = value
        additional_databases = self.t_listify(
            variables.pop('additional_databases')
        )
        for additional_database in additional_databases:
            try:
                name, url = additional_database.split('=', 1)
            except ValueError:
                raise ValueError(
                    (
                        "The databases entry '%s' is incorrect, "
                        "it should be in the form 'name=url'"
                    ) % additional_database
                )
            databases[name] = split_dburl(url)
        variables['databases'] = databases

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

        variables = {}
        for section in self.buildout.keys():
            variables[section] = bunch(
                **dict(normalize_keys(self.buildout[section]))
            )
        variables.update(dict(normalize_keys(self.options)))
        self.fix_databases(variables)
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
        """Create arbitrary boot script.

        This script will also include the eventual code found in
        ``initialization`` and will also set (via ``os.environ``) the
        environment variables found in ``environment-vars``
        """

        # The initialization code is expressed as a list of lines
        initialization = []

        # Gets the initialization code: the tricky part here is to preserve
        # indentation.
        # Since buildout does totally waste whitespace, if one wants to
        # preserve indentation must prefix its lines with '>>> ' or '... '
        raw_value = self.options.get("initialization", "")
        is_indented = False
        indentations = ('>>> ', '... ')
        for line in raw_value.splitlines():
            if line != "":
                if len(initialization) == 0:
                    if line.startswith(indentations[0]):
                        is_indented = True
                else:
                    if is_indented and not line.startswith(indentations[1]):
                        raise zc.buildout.UserError(
                            ("Line '%s' should be indented "
                             "properly but is not") % line
                        )
                if is_indented:
                    line = line[4:]
                initialization.append(line)

        # Gets the environment-vars option and generates code to set the
        # enviroment variables via os.environ
        environment_vars = []
        for line in self.t_listify(self.options.get("environment-vars", "")):
            try:
                var_name, raw_value = line.split(" ", 1)
            except ValueError:
                raise RuntimeError(
                    "Bad djc.recipe environment-vars contents: %s" % line
                )
            environment_vars.append(
                'os.environ["%s"] = r"%s"' % (
                    var_name,
                    raw_value.strip()
                )
            )
        if len(environment_vars) > 0:
            initialization.append("import os")
            initialization.extend(environment_vars)

        __, ws = self.rws
        self._logger.info(
            "Creating script at %s" % (os.path.join(path, name),)
        )
        if len(extra_attr) > 0:
            extras = ", " + ", ".join(extra_attr)
        else:
            extras = ''

        if len(initialization) > 0:
            initialization = "\n"+"\n".join(initialization)+"\n"
        else:
            initialization = ""

        return zc.buildout.easy_install.scripts(
            [(name, module, attr)],
            ws, self.options['executable'],
            path,
            extra_paths = self.extra_paths,
            initialization=initialization,
            arguments = "'%s'%s" % (
                "%s.%s" % (
                    os.path.basename(self.module_path.rstrip(os.sep)),
                    os.path.splitext(_settings_name)[0].split('$py')[0]
                ),
                extras
            )
        )

    def create_manage_script(self):
        """Creates the ``bin/${:__name__}`` script
        """
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
        extras = []
        if 'wsgi-logfile' in self.options:
            extras.append(
                "logfile = '%s'" % os.path.join(
                    self.buildout['buildout']['directory'],
                    self.options['wsgi-logfile']
                )
            )
            if 'wsgi-loglevel' in self.options:
                extras.append(
                    "loglevel = '%s'" % self.options['wsgi-loglevel'].upper()
                )
        script = self._create_script(
            'app.py',
            self.module_path,
            'djc.recipe.wsgi',
            'main',
            extras
        )
        zc.buildout.easy_install.script_template = _script_template
        return script

    def install_project(self):
        if 'project' in self.options:
            __, ws = self.rws
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

    def copy_origin(self, origins, destination, link = False):
        copier = Copier(link=link)
        for origin in origins:
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
                __, ws = self.rws
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
                target = os.path.join(destination, components[2])
            else:
                target = destination
            copier.copy(orig_directory, target)
        try:
            copier.execute()
        except OSError, e:
            raise zc.buildout.UserError(
                "Failed to copy %s into '%s': %s" % (
                    ', '.join([ "'%s'" % o for o in origins ]),
                    destination,
                    e
                )
            )

    def create_static(self, prefix):
        media_directory = os.path.join(
            self.buildout['buildout']['directory'],
            self.options['%s-directory' % prefix]
        )
        origin_option = '%s-origin' % prefix
        link_option = 'link-%s-origin' % prefix
        if origin_option in self.options:
            if not os.path.isdir(media_directory):
                self._logger.info(
                    "Making %s directory '%s'" % (prefix, media_directory)
                )
                os.makedirs(media_directory)
            link = (self.options.get(link_option, 'false').lower() == 'true')
            self.copy_origin(
                self.options[origin_option].split(),
                media_directory,
                link
            )
        else:
            if not os.path.isdir(media_directory):
                self._logger.info(
                    "Making empty %s directory '%s'" % (prefix,
                                                        media_directory)
                )
                os.makedirs(media_directory)
        return [ media_directory ]

    def create_project(self):
        project_dir = self.module_path
        if not os.path.exists(project_dir):
            self._logger.debug("Creating %s" % project_dir)
            os.makedirs(project_dir)
        if not os.path.isdir(project_dir):
            raise zc.buildout.UserError(
                "Can't install %s: %s is not a directory!" % (
                    self.name, project_dir
                )
            )
        self._logger.info("Making %s a module" % self.module_path)
        touch(os.path.join(self.module_path, '__init__.py'), content = '#')
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
        self.create_static('media') # we don't tell buildout we have created
                                    # this directory so it's not deleted before
                                    # update/reinstallation
        files = (
            self.create_project() +
            self.create_static('static') +
            self.create_manage_script()
        )
        if self.t_boolify(self.options.get('wsgi', 'false')):
            files += self.create_wsgi_script()
        return tuple(files)

    update = install
