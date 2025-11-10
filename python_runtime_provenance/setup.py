"""
Setup script for Python Runtime Provenance Tracking System
Install this package system-wide to enable runtime tracking for all Python applications.
"""

from setuptools import setup, find_packages

setup(
    name='python-runtime-provenance',
    version='1.0.0',
    description='Runtime-level Server-Side Tracking (SST) Detection via Python Instrumentation',
    author='Enas Batarfi',
    author_email='',
    packages=find_packages(),
    py_modules=['sitecustomize'],
    install_requires=[
        # No dependencies - works with standard library
        # Optional: flask, sqlalchemy, requests, openai (if available)
    ],
    entry_points={
        'console_scripts': [
            'enable-provenance-tracking=python_runtime_provenance.cli:enable',
            'disable-provenance-tracking=python_runtime_provenance.cli:disable',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Security',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
    ],
    python_requires='>=3.8',
)
