"""Define metadata for AMP Renderer."""

# Third Party
import setuptools

with open("README.md", "r") as readme_file:
    long_description = readme_file.read()

setuptools.setup(
    name="amp-renderer",
    version="2.0.1",
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
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)
