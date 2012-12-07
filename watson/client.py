# -*- coding: utf-8 -*-

import xmlrpclib
import yaml

from . import core


class WatsonClient(xmlrpclib.ServerProxy):

    def __init__(self):
        self.endpoint = ('localhost', 0x221B)
        xmlrpclib.ServerProxy.__init__(self, 'http://%s:%s/' % self.endpoint)

    def watch(self, working_dir="."):
        project_dir = core.find_project_directory(working_dir)
        config_file = project_dir / core.CONFIG_FILENAME

        if not config_file.exists():
            raise core.WatsonError('config %s does not exist' % config_file)

        with open(config_file) as f:
            config = yaml.load(f)

        # Normalize config
        config.setdefault('name', project_dir.name)
        if not isinstance(config['script'], list):
            config['script'] = [config['script']]

        self.add_project(working_dir, config)

def main():
    pass
