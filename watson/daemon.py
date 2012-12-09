# -*- coding: utf-8 -*-

from __future__ import absolute_import

import os
import path
import sys
import time

from daemon import runner

from . import core


WATSON_DIR = path.path('~/.watson').expand()


class _DaemonRunner(runner.DaemonRunner):
    """Modified DaemonRunner that checks pidfile before opening a context."""

    def parse_args(self, args=None):
        self.action_funcs[u'start'] = self._start
        self.action_funcs[u'stop'] = self._stop
        self.action_funcs[u'restart'] = self._restart

    def _start(self):
        if self.pidfile.read_pid() is not None:
            raise runner.DaemonRunnerStartFailureError(
                u"PID file %r already locked" % self.app.pidfile_path)

        return super(_DaemonRunner, self)._start()

    def do_action(self, action=None):
        self.action = action
        func = self._get_action_func()
        func()


class WatsonDaemon(object):

    def __init__(self):
        self.pidfile_path = WATSON_DIR / 'pid'
        self.stdin_path = path.path('/dev/null')
        self.stdout_path = WATSON_DIR / 'stdout'
        self.stderr_path = WATSON_DIR / 'stderr'
        self.pidfile_timeout = 0

        # Create watson directory if it is not already there
        WATSON_DIR.mkdir_p()

    def run(self):
        server = None
        try:
            server = core.WatsonServer()
            server._start()
        except KeyboardInterrupt:
            pass
        finally:
            if server is not None:
                server.shutdown()
                server._join()

    def perform(self, action, fork=False):
        if not fork or os.fork() == 0:
            _DaemonRunner(self).do_action(action)
        elif fork:
            time.sleep(1)


def main():
    if len(sys.argv) < 2:
        return

    command = sys.argv[1]

    if command in ['run']:
        WatsonDaemon().run()

if __name__ == '__main__':
    main()
