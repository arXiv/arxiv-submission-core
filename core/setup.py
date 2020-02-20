"""Install arXiv submission core package."""

from setuptools import setup, find_packages
from arxiv.release.dist_version import get_version

setup(
    name='arxiv-submission-core',
    version=get_version('arxiv-submission-core'),
    packages=[f'arxiv.{package}' for package
              in find_packages('arxiv')],
    zip_safe=False,
    setup_requires=['arxiv-base>=0.16.6rc8'],
    install_requires=[
        'arxiv-base>=0.16.6rc8',
        'arxiv-auth>=0.4.2rc1',
        'flask',
        'mysqlclient',
        'bleach',
        'unidecode',
        'python-dateutil',
        'sqlalchemy',
        'flask-sqlalchemy',
        'dataclasses',
        'celery==4.1.0',
        'kombu==4.1.0',
        'redis==2.10.6',
        'mypy_extensions==0.4.1',
        'requests==2.21.0',
        'semver==2.8.1',
        'retry==0.9.2',
        'pytz==2018.7',
        'backports-datetime-fromisoformat==1.0.0',
        'typing_extensions'
    ],
    include_package_data=True
)
