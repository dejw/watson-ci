# -*- coding: utf-8 -*-

from __future__ import absolute_import

import atexit
import logging
import os
import path
import re
import SimpleXMLRPCServer
import sched
import threading
import time
import yaml

from fabric import context_managers
from fabric import decorators
from fabric import operations
from multiprocessing import pool
from stuf import collects
from watchdog import events
from watchdog import observers


logging.basicConfig(level=logging.DEBUG, format='%(levelname)s %(message)s')


VERSION = "0.1.0"

CONFIG_FILENAME = '.watson.yaml'
DEFAULT_PROJECT_INDICATORS = [CONFIG_FILENAME, '.vip', 'setup.py']

DEFAULT_GLOBAL_CONFIG_FILE = path.path('~/.watson/config.yaml').expand()
DEFAULT_CONFIG = {
    'endpoint': 'localhost:%s' % 0x221B,
    'ignore': ['.git/.*', '.*.pyc'],
    'build_timeout': 3
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


def load_config(config_file):
    logging.info('Loading config: %s', config_file)
    config_file = path.path(config_file).abspath()
    project_dir = config_file.dirname()

    if not config_file.exists():
        raise WatsonError('config %s does not exist' % config_file)

    with open(config_file) as f:
        config = yaml.load(f)

    return config


def load_config_safe(config_file):
    try:
        return load_config(config_file)
    except WatsonError:
        return {}


class EventScheduler(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)
        self._sched = sched.scheduler(time.time, self.delay)
        self._is_finished = False
        self._condition = threading.Condition()
        self._join_event = threading.Event()

    def delay(self, timeout):
        with self._condition:
            self._condition.wait(timeout)

    @property
    def is_finished(self):
        with self._condition:
            return self._is_finished

    def schedule(self, event, delay, function):
        with self._condition:
            logging.info('Scheduling %s in %ss', function.__name__, delay)
            if event is not None:
                self._sched.cancel(event)

            self._condition.notify()
            return self._sched.enter(delay, 1, function, [])

    def stop(self):
        with self._condition:
            logging.info('Stopping event scheduler')
            self._is_finished = True
            for event in self._sched.queue:
                self._sched.cancel(event)

            self._condition.notify()

    def join(self, timeout=None):
        self._join_event.wait(timeout)

    def run(self):
        logging.info('Starting event scheduler')

        while not self.is_finished:
            self._sched.run()
            with self._condition:
                if not self._is_finished:
                    logging.info('Queue is empty')
                    self._condition.wait()

        self._join_event.set()
        logging.info('Event scheduler stopped')


class Config(collects.ChainMap):

    _KEYS_TO_WRAP = ['ignore', 'script']

    def __init__(self, *configs):
        if not configs:
            configs.append(DEFAULT_CONFIG)
        super(Config, self).__init__(*configs)

    def __getitem__(self, item):
        value = super(Config, self).__getitem__(item)

        if item in self._KEYS_TO_WRAP and not isinstance(value, list):
            value = [value]

        return value

    def push(self, config):
        new_config = self.new_child()
        new_config.update(config)
        return new_config

    def replace(self, config):
        self.maps[0] = config

    def __getattr__(self, attr):
        return self.__getitem__(attr)


class ProjectWatcher(events.FileSystemEventHandler):

    # TODO(dejw): should expose some stats (like how many times it was
    #             notified) or how many times it succeeed in testing etc.

    def __init__(self, config, working_dir, scheduler, builder, observer):
        super(ProjectWatcher, self).__init__()

        self._event = None

        self.name = get_project_name(working_dir)
        self.working_dir = path.path(working_dir)
        self.set_config(config)

        self._last_status = (None, None)
        self._create_notification()

        self._scheduler = scheduler
        self._builder = builder
        self._observer = observer

        # TODO(dejw): allow to change observing patterns (and recursiveness)
        self._watch = observer.schedule(self, path=working_dir, recursive=True)

        logging.info('Observing %s', working_dir)

    def __repr__(self):
        return '<ProjectWatcher %s(%s)>' % (self.name, self.working_dir)

    @property
    def script(self):
        return self._config['script']

    def set_config(self, config):
        self._config = config

    def shutdown(self):
        logging.info('Shuting down project: %r', self)
        self._hide_notification()
        self._observer.unschedule(self._watch)

    def on_any_event(self, event):
        logging.debug('Event: %r', event)

        event_path = event.src_path[len(self.working_dir):].lstrip('/')
        for ignore in self._config['ignore']:
            if re.match(ignore, event_path):
                return

        # Automatically pickup config changes
        logging.debug(event_path)
        if event_path == CONFIG_FILENAME:
            self._config.replace(load_config(event.src_path))

        self.schedule_build()

    def schedule_build(self, timeout=None):
        """Schedules a building process in configured timeout."""

        if timeout is None:
            timeout = self._config['build_timeout']

        logging.debug('Scheduling a build in %ss', timeout)
        self._event = self._scheduler.schedule(
            self._event, timeout, self.build)

    def build(self):
        """Builds the project and shows notification on result."""
        logging.info('Building %s (%s)', self.name, self.working_dir)
        self._event = None
        status = self._builder.execute_script(self.working_dir, self.script)
        self._show_notification(status)

    def _create_notification(self):
        try:
            import pynotify
            self._notification = pynotify.Notification('')
            self._notification.set_timeout(3)
        except ImportError:
            pass

    def _hide_notification(self):
        self._notification.close()

    def _show_notification(self, status):
        succeeed, result = status
        output = '\n'.join([result.stdout.strip(), result.stderr.strip()])
        output = output

        if not succeeed:
            self._notification.update(
                'Build of %s has failed' % self.name, output, 'dialog-error')
        else:
            self._notification.update(
                'Build of %s was successful' % self.name, output,
                'dialog-apply')

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
        self._config = Config(load_config_safe(DEFAULT_GLOBAL_CONFIG_FILE))
        self._projects = {}

        self._builder = ProjectBuilder()
        self._observer = observers.Observer()
        self._scheduler = EventScheduler()
        self._init_pynotify()

        # TODO(dejw): read (host, port) from config in user's directory
        self.endpoint = ('localhost', 0x221B)
        self._api = SimpleXMLRPCServer.SimpleXMLRPCServer(
            self.endpoint, allow_none=True)
        self._api.register_instance(self)

    def _start(self):
        logging.info('Server listening on %s' % (self.endpoint,))
        self._scheduler.start()
        self._observer.start()
        self._api.serve_forever()

    def _join(self):
        self._api.shutdown()

    def _init_pynotify(self):
        logging.info('Configuring pynotify')
        try:
            import pynotify
            pynotify.init('Watson')
            assert pynotify.get_server_caps() is not None
        except ImportError:
            logging.error('pynotify not found; notifications disabled')

    def hello(self):
        return 'Watson server %s' % VERSION

    def shutdown(self):
        logging.info('Shuting down')

        for project in self._projects.itervalues():
            project.shutdown()

        self._api.server_close()
        self._observer.stop()
        self._scheduler.stop()

        self._observer.join()
        self._scheduler.join()

    def add_project(self, working_dir, config):
        try:
            logging.info('Adding a project: %s', working_dir)

            project_name = get_project_name(working_dir)
            config = self._config.push(config)

            if project_name not in self._projects:
                self._projects[project_name] = ProjectWatcher(
                    config, working_dir, self._scheduler, self._builder,
                    self._observer)

            else:
                self._projects[project_name].set_config(config)

            self._projects[project_name].schedule_build(0)
        except:
            import traceback
            traceback.print_exc()
