#!/usr/bin/env python

"""
AUVSI airborne: Code for the airborne computer of the AUVSI drone.

Authors:
Amit Aides <amitibo@tx.technion.ac.il>
URL: <http://bitbucket.org/amitibo/auvsi>
License: See attached license file
"""

from setuptools import setup
import platform
import glob
import os

NAME = 'AUVSIairborne'
PACKAGE_NAME = 'AUVSIairborne'
PACKAGES = [PACKAGE_NAME]
VERSION = '0.1'
DESCRIPTION = 'Code for airborne computer of the AUVSI drone.'
LONG_DESCRIPTION = """
airborne computer of the AUVSI drone.
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
        'scripts/start_auvsi.py',
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
        scripts=choose_scripts(),
    )


if __name__ == '__main__':
    main()
