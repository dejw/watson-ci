# -*- coding: utf-8 -*-

import __builtin__
import mox
import path
import yaml

from . import core
from . import client
from . import test_helper
from .test_helper import unittest


class TestWatsonClient(test_helper.TestBase):

    def test_watch(self):
        working_dir = path.path(__file__).dirname()
        working_dir /= '../fixtures/project1/some_dir'
        project_dir = unicode((working_dir / '..').abspath())

        config = core.load_config(working_dir / '..' / core.CONFIG_FILENAME)

        cl = client.WatsonClient()
        cl.add_project = self.mox.CreateMockAnything()
        cl.add_project(project_dir, config)

        self.mox.ReplayAll()

        # when...
        cl.watch(working_dir)

        self.mox.VerifyAll()

    def test_watch_raise_WatsonError_without_config(self):
        cl = client.WatsonClient()
        working_dir = (path.path(__file__).dirname()
                       / '../fixtures/project_no_config')

        with self.assertRaises(core.WatsonError):
            cl.watch(working_dir)


if __name__ == '__main__':
    unittest.main()
