#!/usr/bin/env python2

from setuptools import setup, find_packages

SETUP = {
    'name': 'jujucrashdump',
    'version': '0.0.0',
    'author': 'Juju Developers',
    'author_email': 'juju@lists.ubuntu.com',
    'description': 'Tool for gathering logs and other debugging info from a Juju Model',
    'url': 'https://github.com/juju-solutions/jujucrashdump',
    'packages': find_packages(
        exclude=["setup.py"]),
    'scripts': [
        'juju-crashdump',
    ],
    'install_requires': ['PyYAML']
}

if __name__ == '__main__':
    setup(**SETUP)
