"""Define metadata for AMP Renderer."""

from pathlib import Path

import setuptools

long_description = Path("README.md").read_text(encoding="utf-8")

setuptools.setup(
    name="amp-renderer",
    version="2.2.0",
    author="Chase Finch",
    author_email="chase@finch.email",
    description="Unofficial Python port of server-side rendering from AMP Optimizer",
    keywords=["AMP", "AMP Optimizer", "server-side rendering"],
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/chasefinch/amp-renderer",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
)
