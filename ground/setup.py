#!/usr/bin/env python

"""
AUVSIground: Code for the ground station of the AUVSI drone.

Authors:
Amit Aides <amitibo@tx.technion.ac.il>
URL: <http://bitbucket.org/amitibo/auvsi>
License: See attached license file
"""

from setuptools import setup
import platform
import glob
import os

NAME = 'AUVSIground'
PACKAGE_NAME = 'AUVSIground'
PACKAGES = [PACKAGE_NAME]
VERSION = '0.1'
DESCRIPTION = 'Code for groung station of the AUVSI drone.'
LONG_DESCRIPTION = """
groung station of the AUVSI drone.
"""
AUTHOR = 'Amit Aides'
EMAIL = 'amitibo@tx.technion.ac.il'
KEYWORDS = []
LICENSE = 'GPLv3'
CLASSIFIERS = [
    'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
    'Development Status :: 2 - Pre-Alpha',
    'Topic :: Scientific/Engineering'
]
URL = "http://bitbucket.org/amitibo/auvsi"


def choose_scripts():
    
    scripts = [
        'scripts/start_ground.py',
    ]

    return scripts


def main():
    """main setup function"""
    
    s = setup(
        name=NAME,
        version=VERSION,
        description=DESCRIPTION,
        long_description=LONG_DESCRIPTION,
        author=AUTHOR,
        author_email=EMAIL,
        url=URL,
        keywords=KEYWORDS,
        classifiers=CLASSIFIERS,
        license=LICENSE,
        packages=PACKAGES,
        package_data={PACKAGE_NAME: ['resources/*.kv']},
        scripts=choose_scripts(),
    )


if __name__ == '__main__':
    main()
