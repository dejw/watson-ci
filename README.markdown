# Watson CI

[![Build Status](https://travis-ci.org/dejw/watson-ci.png)](https://travis-ci.org/dejw/watson-ci)

`watson` is a simple continuous integration server that helps you build
your projects constantly while you edit the files.

![dr Watson](http://2.bp.blogspot.com/--OeE_SOXm8s/Tief56DVOVI/AAAAAAAABSs/eUTLMpXrq_I/s1600/dr-watson.png)

(The image above is available on [www.evilspacerobot.com](http://www.evilspacerobot.com))

## Philosophy

In its concept `watson` watches for changes made in the filesystem of your
project, and on this basis, runs configured test (or build) commands to check
if everything is still fine and all your test pass.

In its usage design it is similar to [Travis CI](https://github.com/travis-ci/travis-ci) server.

## Configuration

Each project should provide a file named `.watson.yaml` (note the dot) with its
configuration, for example:

    script:
        - nosetests
        - pep8
    ignore:
        - .*.pyc

The only requirement is that **the script should use an exit code 0 on
success** and anything else will be considered as failure.

Commands will be executed with relative to the directory where filesystem
recently changed.

Example configuration (used by `watson` project itself) can be found
[here](https://github.com/dejw/watson-ci/blob/master/.watson.yaml).

## Usage

To add your project to watson use:

    watson watch

in any directory of your project. `.watson.yaml` fill be searched up the root
directory and your project configuration will be updated in the server.

Config changes are detected and picked up automatically.

As soon as your project is built, server will show a notification about its
status. It uses `pynotify` library to handle it so they look as follows:

![](http://i.imgur.com/uInH4.png)  
![](http://i.imgur.com/zRG93.png)

### Portability

For now `watson` was tested only under Ubuntu, and does not have any kind of abstraction
for notification support. Feel free to contribute if you are insterested in other
notification systems.

## Server management

Also server will be started if needed using configuration in
`~/.watson/config.yaml`.

You can manage state of the server as well:

    watson start|stop|restart

By default `watson` listens on port `0x221B` (`8731`), and exposes a simple XMLRPC API.

## Installation

Simply type the following command into terminal to install the latest released
version:

    pip install watson-ci [--upgrade]

## Contribution

Improvement ideas are welcome.

Feel free to file a bug report, or send a pull request. I will try my best to
look into it and merge your changes, or I'll give you commit rights if you will.