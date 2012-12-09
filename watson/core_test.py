# -*- coding: utf-8 -*-

import collections
import its
import mox
import path
import SimpleXMLRPCServer
import tempfile

from fabric import context_managers
from fabric import operations
from watchdog import observers

from . import core
from . import test_helper
from .test_helper import unittest


class TestFindProjectDirectory(unittest.TestCase):

    def test_simple(self):
        look_for = ['requirements.txt']
        start = path.path(__file__).dirname()

        directory = core.find_project_directory(start, look_for=look_for)

        self.assertEqual(start.parent, directory)

    def test_WatsonError_dir_is_not_part_of_project(self):
        with self.assertRaises(core.WatsonError):
            _ = core.find_project_directory(tempfile.gettempdir())


class HeadlessProjectWatcher(core.ProjectWatcher):

    def _create_notification(self):
        pass

    def _show_notification(self, status):
        self._last_status = status

    def _hide_notification(self):
        pass


class TestProjectWatcher(test_helper.TestBase):

    @classmethod
    def setUpClass(self):
        self._project_dir = core.find_project_directory(
            path.path(__file__).dirname())

    def setUp(self):
        super(TestProjectWatcher, self).setUp()

        self.directory = 'a directory'
        self.watch = 'a watch'

        self.observer_mock = self.mox.CreateMock(observers.Observer)
        self.worker_mock = self.mox.CreateMock(core.ProjectBuilder)
        self.scheduler_mock = self.mox.CreateMock(core.EventScheduler)

        (self.observer_mock.schedule(
            mox.IsA(core.ProjectWatcher), path=self.directory, recursive=True)
            .AndReturn(self.watch))

    def get_watcher(self, config=None):
        return HeadlessProjectWatcher(
            config or {}, self.directory, self.scheduler_mock,
            self.worker_mock, self.observer_mock)

    def test_init(self):
        self.mox.ReplayAll()

        self.get_watcher()

        self.mox.VerifyAll()

    def test_shutdown(self):
        self.observer_mock.unschedule(self.watch)
        self.mox.ReplayAll()

        self.get_watcher().shutdown()

        self.mox.VerifyAll()

    def test_build(self):
        status = (True, None)
        (self.worker_mock.execute_script(self.directory, ['nosetests'])
            .AndReturn(status))
        self.mox.ReplayAll()

        watcher = self.get_watcher({'name': 'test', 'script': ['nosetests']})
        watcher.build()

        self.mox.VerifyAll()
        self.assertEqual(status, watcher._last_status)


class HeadlessWatsonServer(core.WatsonServer):

    def _init_pynotify(self):
        pass


class TestWatsonServer(test_helper.TestBase):

    def setUp(self):
        super(TestWatsonServer, self).setUp()

        self.mox.StubOutClassWithMocks(SimpleXMLRPCServer,
                                       "SimpleXMLRPCServer")

        hostport = ("localhost", 0x221B)
        self.server_mock = SimpleXMLRPCServer.SimpleXMLRPCServer(
            hostport, allow_none=True)
        self.server_mock.register_instance(mox.IsA(core.WatsonServer))

        self.mox.StubOutClassWithMocks(observers, "Observer")
        self.observer_mock = observers.Observer()

        self.mox.StubOutClassWithMocks(core, "EventScheduler")
        self.scheduler_mock = core.EventScheduler()

    def test_init(self):
        self.mox.ReplayAll()

        HeadlessWatsonServer()

        self.mox.VerifyAll()

    def test_start(self):
        self.server_mock.serve_forever()
        self.observer_mock.start()
        self.scheduler_mock.start()

        self.mox.ReplayAll()

        HeadlessWatsonServer()._start()

        self.mox.VerifyAll()

    def test_shutdown(self):
        self.server_mock.server_close()
        self.observer_mock.stop()
        self.observer_mock.join()
        self.scheduler_mock.stop()
        self.scheduler_mock.join()

        self.mox.ReplayAll()

        HeadlessWatsonServer().shutdown()

        self.mox.VerifyAll()

    def test_hello(self):
        self.mox.ReplayAll()

        version = HeadlessWatsonServer().hello()

        self.mox.VerifyAll()
        self.assertIn(core.VERSION, version)


class ResultMock(collections.namedtuple('ResultMock', ['succeeded', 'msg'])):
    pass


class TestProjectBuilder(test_helper.TestBase):

    def setUp(self):
        super(TestProjectBuilder, self).setUp()

        self.working_dir = 'a directory'

        lcd_mock = self.mox.CreateMockAnything()
        lcd_mock.__enter__()
        lcd_mock.__exit__(mox.IgnoreArg(), mox.IgnoreArg(), mox.IgnoreArg())
        self.mox.StubOutWithMock(context_managers, 'lcd')
        context_managers.lcd(self.working_dir).AndReturn(lcd_mock)

    def _stubout_local(self, script, results):
        self.mox.StubOutWithMock(operations, 'local')
        for command, result in zip(script, results):
            operations.local(command, capture=True).AndReturn(
                ResultMock(result, command))

    def test_execute_script_internal(self):
        script = ['echo 1', 'echo 2']
        self._stubout_local(script, [True, True])

        self.mox.ReplayAll()

        worker = core.ProjectBuilder()
        result = worker._execute_script_internal(self.working_dir, script)

        self.mox.VerifyAll()
        self.assertEqual((True, ResultMock(True, script[-1])), result)

    def test_execute_runs_until_first_failure(self):
        script = ['echo 1', 'echo 2', 'echo 3']

        # only first two commands are passed to operations.local
        self._stubout_local(script[:2], [True, False])
        self.mox.ReplayAll()

        worker = core.ProjectBuilder()
        result = worker._execute_script_internal(self.working_dir, script)

        self.mox.VerifyAll()
        self.assertEqual((False, ResultMock(False, script[1])), result)


class TestConfig(unittest.TestCase):

    def test_default_config(self):
        try:
            core.Config()['ignore']
            core.Config()['build_timeout']
        except KeyError:
            self.fail('Did not expect KeyError with default config')


if __name__ == '__main__':
    unittest.main()
