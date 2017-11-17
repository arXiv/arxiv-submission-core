# arxiv/submit-api

FROM ubuntu:zesty

RUN apt-get update && apt-get install -y \
    ca-certificates \
    wget \
    gcc \
    g++ \
    libpython3.6 \
    python3.6 \
    python3.6-dev \
    python3.6-venv \
    nginx \
 && rm -rf /var/lib/apt/lists/*

RUN wget https://bootstrap.pypa.io/get-pip.py
RUN python3.6 get-pip.py

RUN pip install uwsgi

# Add Python consumer and configuration.
ADD requirements.txt /opt/arxiv/requirements.txt
RUN pip install -U pip
RUN pip install -r /opt/arxiv/requirements.txt

ADD . /opt/arxiv/
ADD gateway/etc/nginx.conf /etc/nginx/conf.d/submit.conf

ENV JWT_SECRET "foosecret"
EXPOSE 8000

WORKDIR /opt/arxiv
RUN chmod +x /opt/arxiv/start_sim.sh
CMD /bin/sh start_sim.sh
#CMD /bin/bash
