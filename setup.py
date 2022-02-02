#!/usr/bin/env python
import os

from setuptools import setup, find_packages

sys_conf_dir = os.getenv("SYSCONFDIR", "/etc")


classes = """
    Development Status :: 4 - Beta
    Intended Audience :: Developers
    Programming Language :: Python
    Programming Language :: Python :: 3
    Programming Language :: Python :: 3.6
    Programming Language :: Python :: Implementation :: CPython
    Programming Language :: Python :: Implementation :: PyPy
    Operating System :: OS Independent
"""
classifiers = [s.strip() for s in classes.split('\n') if s]


setup(
    name='tux-control-plugin-xscreensaver',
    version='0.0.9',
    description='Tux Control XScreensaver plugin',
    long_description=open('README.md').read(),
    author='Adam Schubert',
    author_email='adam.schubert@sg1-game.net',
    url='https://github.com/tux-control/plugin_xscreensaver',
    license='GPL-3',
    classifiers=classifiers,
    packages=find_packages(exclude=['tests', 'tests.*']),
    install_requires=[
        'xmltodict',
        'xscreensaver_config',
        'tux-control'
    ],
    test_suite="tests",
    tests_require=[],
    data_files=[
        (os.path.join(sys_conf_dir, 'tux-control', 'plugin.d'), [
            'etc/tux-control/plugin.d/xscreensaver.yml',
        ])
    ]
)
