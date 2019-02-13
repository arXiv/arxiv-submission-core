"""Install arXiv submission core package."""

from setuptools import setup, find_packages

setup(
    name='arxiv-submission-core',
    version='0.6.2rc4',
    packages=[f'arxiv.{package}' for package
              in find_packages('arxiv')],
    zip_safe=False,
    install_requires=[
        'arxiv-base',
        'arxiv-auth',
        'flask',
        'mysqlclient',
        'bleach',
        'unidecode',
        'python-dateutil',
        'sqlalchemy',
        'dataclasses',
        'celery==4.1.0',
        'kombu==4.1.0',
        'redis==2.10.6'
    ]
)
