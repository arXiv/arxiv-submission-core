# arxiv/submission-authorization
#
# This is a simple mockup for an eventual authorization service.

FROM arxiv/base

RUN pip install uwsgi

# Add Python consumer and configuration.
ADD . /opt/arxiv/
WORKDIR /opt/arxiv
RUN pip install -U pip
RUN pip install -e git+git://github.com/cul-it/arxiv-base.git@develop#egg=arxiv-base
RUN pip install -r /opt/arxiv/requirements.txt


ENV JWT_SECRET "foo"
EXPOSE 8000

#CMD /bin/bash

CMD uwsgi --http-socket :8000 -w auth -M \
        -t 3000 --manage-script-name \
        --processes 8 --threads 1 --async 100 --ugreen \
