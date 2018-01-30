from setuptools import setup, find_packages

setup(
    name='arxiv-authorization',
    version='0.1',
    packages=find_packages(exclude=['tests.*']),
    zip_safe=False,
    install_requires=[
        "PyJWT==1.5.3",
        "Flask==0.12.2"
    ],
    dependency_links=[
        "https://github.com/cul-it/arxiv-base.git@develop#egg=arxiv-base",
    ]
)
