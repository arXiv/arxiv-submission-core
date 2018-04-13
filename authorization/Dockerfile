# arxiv/submission-authorization
#
# This is a simple mockup for an eventual authorization service.

FROM arxiv/base

WORKDIR /opt/arxiv

# Add Python consumer and configuration.
ADD Pipfile /opt/arxiv/Pipfile
ADD Pipfile.lock /opt/arxiv/Pipfile.lock
RUN pip install pipenv
RUN pipenv install
RUN pipenv install uwsgi

ADD . /opt/arxiv/

ENV JWT_SECRET "foo"
EXPOSE 8000

#CMD /bin/bash

CMD pipenv run uwsgi --http-socket :8000 -w auth -M \
        -t 3000 --manage-script-name \
        --processes 8 --threads 1 --async 100 --ugreen \
