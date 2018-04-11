#!/bin/bash

pipenv run python initialize_db.py
pipenv run uwsgi "$@"
