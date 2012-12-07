# -*- coding: utf-8 -*-

import atexit
import logging
import os
import path
import SimpleXMLRPCServer
import threading

from fabric import context_managers
from fabric import decorators
from fabric import operations
from multiprocessing import pool
from stuf.collects import ChainMap
from watchdog import events
from watchdog import observers

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')


CONFIG_FILENAME = '.watson.yaml'
DEFAULT_PROJECT_INDICATORS = [CONFIG_FILENAME, '.vip', 'setup.py']

DEFAULT_CONFIG = {
    'ignore': ['.git'],
    'build_timeout': 5
}


class WatsonError(StandardError):
    pass


def find_project_directory(start=".", look_for=None):
    """Finds a directory that looks like a project directory.

    The search is performed up in the directory tree, and is finished when
    one of the terminators is found.

    Args:
        start: a path (directory) from where the search is started
            "." by default
        look_for: a list of search terminators,
            core.DEFAULT_PROJECT_INDICATORS by default

    Returns:
        A path to a directory that contains one of terminators

    Raises:
        WatsonError: when no such directory can be found
    """
    look_for = set(look_for or DEFAULT_PROJECT_INDICATORS)

    directory = path.path(start).abspath()

    while directory.parent != directory:
        items = os.listdir(directory)
        if any(i in look_for for i in items):
            return directory

        directory = directory.parent

    raise WatsonError('%s does not look like a project subdirectory' % start)


def get_project_name(working_dir):
    """Returns a project name from given working directory."""
    return path.path(working_dir).name


class WatsonConfig(ChainMap):

    _KEYS_TO_WRAP = ['ignore', 'script']

    def __init__(self, config):
        super(WatsonConfig, self).__init__(config, DEFAULT_CONFIG)

    def __getitem__(self, item):
        value = super(WatsonConfig, self).__getitem__(item)

        if item in self._KEYS_TO_WRAP and not isinstance(value, list):
            value = [value]

        return value

    def __getattr__(self, attr):
        return self.__getitem__(attr)


class ProjectWatcher(events.FileSystemEventHandler):

    # TODO(dejw): should expose some stats (like how many times it was
    #             notified) or how many times it succeeed in testing etc.

    def __init__(self, config, working_dir, worker, observer):
        self._build_timer = None

        self.name = get_project_name(working_dir)
        self.working_dir = working_dir
        self.set_config(config)

        self._last_status = (None, None)
        self._create_notification()

        self._worker = worker
        self._observer = observer
        # TODO(dejw): allow to change observing patterns (and recursiveness)
        self._watch = observer.schedule(self, path=working_dir, recursive=True)

        logging.info('Observing %s', working_dir)

    @property
    def script(self):
        return self._config['script']

    def set_config(self, config):
        self._config = WatsonConfig(config)

        if self._build_timer is not None:
            self._build_timer.cancel()

        self._build_timer = threading.Timer(self._config['build_timeout'],
                                            self.build)

    def shutdown(self, observer):
        observer.unschedule(self._watch)

    def on_any_event(self, event):
        logging.info(repr(event))
        self._schedule_building()

    def schedule_building(self):
        self._build_timer.cancel()
        self._build_timer.start()

    def build(self):
        logging.info('Building %s (%s)', self.name, self.working_dir)
        status = self._worker.execute_script(self.working_dir, self.script)
        self._show_notification(status)

    def _create_notification(self):
        import pynotify
        self._notification = pynotify.Notification('')
        self._notification.set_timeout(5)

        # FIXME(dejw): should actually disable all projects and remove
        #      notifications
        atexit.register(self._hide_notification)

    def _hide_notification(self):
        self._notification.close()

    def _show_notification(self, status):
        succeeed, result = status
        output = '\n'.join([result.stdout.strip(), result.stderr.strip()])

        if not succeeed:
            self._notification.update(
                '%s failed' % self.name, output or "No output")
        else:
            self._notification.update('%s back to normal' % self.name,
                                      output)

        self._notification.show()
        self._last_status = status


class ProjectBuilder(object):

    def execute_script(self, working_dir, script):
        return self._execute_script_internal(working_dir, script)

    @decorators.with_settings(warn_only=True)
    def _execute_script_internal(self, working_dir, script):
        succeeded = True
        result = None

        with context_managers.lcd(working_dir):
            for command in script:
                result = operations.local(command, capture=True)
                succeeded = succeeded and result.succeeded
                if not succeeded:
                    break

        return (succeeded, result)


class WatsonServer(object):

    def __init__(self):
        self._worker = ProjectBuilder()
        self._projects = {}
        self._observer = observers.Observer()
        self._observer.start()

        self._init_pynotify()

        # TODO(dejw): read (host, port) from config in user's directory
        hostport = ('localhost', 0x221B)
        self._api = SimpleXMLRPCServer.SimpleXMLRPCServer(hostport,
                                                          allow_none=True)
        self._api.register_instance(self)

        logging.info('Server listening on %s' % (hostport,))
        self._api.serve_forever()

    def _init_pynotify(self):
        logging.info('Configuring pynotify')
        import pynotify
        pynotify.init('Watson')
        assert pynotify.get_server_caps() is not None

    def hello(self):
        return 'World!'

    def shutdown(self):
        logging.info('Shuting down')
        self._api.server_close()
        self._observer.stop()
        self._observer.join()

    def add_project(self, working_dir, config):
        logging.info('Adding a project: %s', working_dir)

        project_name = get_project_name(working_dir)

        if project_name not in self._projects:
            self._projects[project_name] = ProjectWatcher(
                config, working_dir, self._worker, self._observer)

        else:
            self._projects[project_name].set_config(config)

        self._projects[project_name].schedule_building()
