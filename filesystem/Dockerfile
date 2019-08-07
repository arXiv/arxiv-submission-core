# Filesystem app

ARG BASE_VERSION="0.16.1"

FROM arxiv/base:${BASE_VERSION}

WORKDIR /opt/arxiv/

# COPY Pipfile Pipfile.lock /opt/arxiv/
RUN pipenv install arxiv-base==0.16.1 && rm -rf ~/.cache/pip

ENV PATH "/opt/arxiv:${PATH}"

COPY wsgi.py uwsgi.ini /opt/arxiv/
COPY filesystem/ /opt/arxiv/filesystem/

EXPOSE 8000

ENTRYPOINT ["pipenv", "run"]
CMD ["uwsgi", "--ini", "/opt/arxiv/uwsgi.ini"]
