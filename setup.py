# -*- coding: utf-8 -*-

import sys
import os

from setuptools import setup, find_packages
from setuptools.command.install import install as _install


#  Build requirements list
requirements = open('requirements.txt').readlines()

POST_INSTALL_MESSAGE = """
Remember to install pynotify to be able to see system notifications about
build statuses!
"""

def get_info():
    import watson
    return watson.VERSION, open('README.markdown').read()

version, long_description = get_info()

class install(_install):
    def run(self):
        _install.run(self)
        print POST_INSTALL_MESSAGE.strip()


kw = dict(
    name='watson-ci',
    version=version,
    url='https://github.com/dejw/watson-ci/',
    license='BSD',
    author='Dawid Fatyga',
    author_email='dawid.fatyga@gmail.com',
    description='watson is a simple CI server that helps you build your projects continuously',
    long_description=long_description,
    packages=find_packages(),
    zip_safe=False,
    platforms='any',
    install_requires=requirements,
    system_requires=['pynotify'],
    entry_points={
        'console_scripts': [
            'watson = watson.client:main',
        ]
    },
    classifiers=[
        # http://pypi.python.org/pypi?%3Aaction=list_classifiers
        #'Development Status :: 1 - Planning',
        'Development Status :: 2 - Pre-Alpha',
        #'Development Status :: 3 - Alpha',
        #'Development Status :: 4 - Beta',
        #'Development Status :: 5 - Production/Stable',
        #'Development Status :: 6 - Mature',
        #'Development Status :: 7 - Inactive',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: Information Technology',
        'Intended Audience :: Science/Research',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: BSD License',
        'Operating System :: POSIX',
        'Operating System :: MacOS',
        'Operating System :: Unix',
        'Programming Language :: Python',
        'Topic :: System :: Systems Administration',
        'Topic :: Utilities'
    ]
)


if __name__ == '__main__':
    setup(cmdclass={'install': install}, **kw)
