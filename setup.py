# -*- coding: UTF-8 -*-
from __future__ import absolute_import, unicode_literals

# Standard Library
from builtins import bytes  # noqa
from builtins import str  # noqa

# Third Party
import setuptools

with open('README.md', 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name='amp-renderer',
    version='0.1.1',
    author='Chase Finch',
    author_email='chase@finch.email',
    description='Unofficial Python port of server-side rendering from AMP Optimizer',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/chasefinch/amp-renderer',
    packages=setuptools.find_packages(),
    classifiers=[
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=2.7',
    install_requires=[
        'enum34;python_version<"3.4"',
        'future;python_version<="2.7"',
    ],
)
