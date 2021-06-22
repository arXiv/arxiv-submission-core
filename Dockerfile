# arxiv/submission-agent

ARG BASE_VERSION=0.16.6

FROM arxiv/base:${BASE_VERSION}

WORKDIR /opt/arxiv

ENV KINESIS_STREAM="SubmissionEvents" \
    KINESIS_SHARD_ID="0" \
    KINESIS_START_TYPE="TRIM_HORIZON" \
    SUBMISSION_AGENT_DATABASE_URI="" \
    LOGLEVEL=10 \
    JWT_SECRET="foo"

ENV PIPENV_VENV_IN_PROJECT 1

COPY Pipfile Pipfile.lock /opt/arxiv/
RUN pipenv sync && rm -rf ~/.cache/pip

COPY core/ /opt/arxiv/core/
RUN pipenv install /opt/arxiv/core/ && rm -rf ~/.cache/pip
COPY agent/agent/ /opt/arxiv/agent/

ENTRYPOINT ["pipenv", "run"]

CMD ["python", "-m", "agent.consumer"]
# CMD ["celery", "worker", "-A", "agent.worker.worker_app", "--loglevel=INFO", "-E", "--concurrency=2"]
