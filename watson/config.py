# -*- coding: utf-8 -*-

from stuf import collects

DEFAULT_PROJECT_CONFIG = {
    'ignore': ['.git/.*', '.*.pyc'],
    'build_timeout': 3
}


class ProjectConfig(collects.ChainMap):

    _KEYS_TO_WRAP = ['ignore', 'script']

    def __init__(self, config):
        super(ProjectConfig, self).__init__(config, DEFAULT_PROJECT_CONFIG)

    def __getitem__(self, item):
        value = super(ProjectConfig, self).__getitem__(item)

        if item in self._KEYS_TO_WRAP and not isinstance(value, list):
            value = [value]

        return value

    def __getattr__(self, attr):
        return self.__getitem__(attr)
