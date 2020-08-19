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
    version='0.4',
    author='Chase Finch',
    author_email='chase@finch.email',
    description='Unofficial Python port of server-side rendering from AMP Optimizer',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/chasefinch/amp-renderer',
    packages=setuptools.find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=2.7',
)
