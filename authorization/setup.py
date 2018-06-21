"""Install mock arXiv authorization package."""

from setuptools import setup, find_packages

setup(
    name='arxiv-authorization',
    version='0.2.4',
    packages=find_packages(exclude=['test*']),
    zip_safe=False
)
