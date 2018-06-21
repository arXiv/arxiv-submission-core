"""Install arXiv submission event core package."""

from setuptools import setup, find_packages

setup(
    name='arxiv-submission-events',
    version='0.3.1',
    packages=find_packages(exclude=['test*']),
    zip_safe=False
)
