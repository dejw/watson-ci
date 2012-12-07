# -*- coding: utf-8 -*-

import args
import logging
import socket
import xmlrpclib
import yaml

from tornado import options

from . import core
from . import daemon


class WatsonClient(xmlrpclib.ServerProxy):

    def __init__(self):
        self.endpoint = ('localhost', 0x221B)
        xmlrpclib.ServerProxy.__init__(self, 'http://%s:%s/' % self.endpoint,
                                       allow_none=True)

    def watch(self, working_dir="."):
        project_dir = core.find_project_directory(working_dir)
        config_file = project_dir / core.CONFIG_FILENAME

        if not config_file.exists():
            raise core.WatsonError('config %s does not exist' % config_file)

        with open(config_file) as f:
            config = yaml.load(f)

        # Normalize config
        config.setdefault('name', unicode(project_dir.name))
        if not isinstance(config['script'], list):
            config['script'] = [config['script']]

        # TODO(dejw): write a test for marshaling path.path objects
        self.add_project(unicode(project_dir), config)


def main():
    """usage: watson watch

    Repository watcher - watches for filesystem changes of your project and
    constantly builds it and keeps you posted about the build status.

    Commands:

      watch     starts watching a project or updates its status if it was
                already being watched

    """

    if not args.not_files:
        print main.__doc__.strip()

    options.enable_pretty_logging()

    command = args.not_files[0]

    if command == 'watch':
        client = WatsonClient()

        try:
            version = client.hello()
        except socket.error:
            logging.warning('Could not connect to Watson server; Spawning one')
            daemon.WatsonDaemon().perform('start', fork=True)
            try:
                version = client.hello()
            except socket.error:
                raise core.WatsonError('Could not connect to the local watson '
                                       'server at %s' % (client.endpoint,))

        client.watch()

if __name__ == '__main__':
    main()
