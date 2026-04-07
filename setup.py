"""Define metadata for AMP Renderer."""

# Third Party
import setuptools

with open("README.md") as readme_file:
    long_description = readme_file.read()

setuptools.setup(
    name="amp-renderer",
    version="2.1.0",
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
