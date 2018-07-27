"""Install arXiv submission core package."""

from setuptools import setup, find_packages

setup(
    name='arxiv-submission-core',
    version='0.4.2rc1',
    packages=[f'arxiv.{package}' for package
              in find_packages('arxiv', exclude=['*test*'])],
    zip_safe=False
)
