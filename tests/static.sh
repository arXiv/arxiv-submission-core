#!/bin/bash

MYPY_STATUS=$( pipenv run mypy core/arxiv metadata | grep -v "test.*" | grep -v "defined here" | wc -l | tr -d '[:space:]' )
if [ $MYPY_STATUS -ne 0 ]; then MYPY_STATE="failure" && echo "mypy failed"; else MYPY_STATE="success" &&  echo "mypy passed"; fi

curl -u $USERNAME:$GITHUB_TOKEN \
    -d '{"state": "'$MYPY_STATE'", "target_url": "https://travis-ci.org/'$TRAVIS_REPO_SLUG'/builds/'$TRAVIS_BUILD_ID'", "description": "", "context": "code-quality/mypy"}' \
    -XPOST https://api.github.com/repos/$TRAVIS_REPO_SLUG/statuses/$SHA \
    > /dev/null 2>&1
