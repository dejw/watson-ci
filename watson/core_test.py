# -*- coding: utf-8 -*-

import its
import path
import tempfile

try:
    import unittest2 as unittest
except ImportError:
    if not its.py27:
        raise
    import unittest


from . import core


class TestFindProjectDirectory(unittest.TestCase):

    def test_simple(self):
        look_for = ['requirements.txt']
        start = path.path(__file__).dirname()

        directory = core.find_project_directory(start, look_for=look_for)

        self.assertEqual(start.parent, directory)

    def test_WatsonError_dir_is_not_part_of_project(self):
        with self.assertRaises(core.WatsonError):
            _ = core.find_project_directory(tempfile.gettempdir())


if __name__ == '__main__':
    unittest.main()
