FROM centos:centos7

#
# Below we use && chaining and an embedded script in a single RUN
# command to keep image size and layer count to a minimum, while
# the embedded script will make 'docker build' fail fast
# if a package is missing.
#
RUN yum -y update && yum -y install epel-release \
&& yum -y install https://centos7.iuscommunity.org/ius-release.rpm \
&& yum -y update --security \
&& echo $'#!/bin/bash\n\
PKGS_TO_INSTALL=$(cat <<-END\n\
  ca-certificates\n\
  wget\n\
  gcc\n\
  gcc-c++ \n\
  python36u\n\
  python36u-devel\n\
  git\n\
END\n\
)\n\
for pkg in ${PKGS_TO_INSTALL}; do\n\
  # Stop executing if at least one package is not available:\n\
  yum info ${pkg} || {\n\
    echo "yum could not find package ${pkg}"\n\
    exit 1\n\
  }\n\
done\n\
yum -y install ${PKGS_TO_INSTALL}\n' >> /tmp/safe_yum.sh \
&& /bin/bash /tmp/safe_yum.sh \
&& yum clean all

RUN wget https://bootstrap.pypa.io/get-pip.py \
  && python3.6 get-pip.py

RUN pip install uwsgi

ADD gateway/nginx.repo /etc/yum.repos.d/nginx.repo
RUN yum -y update && yum -y install nginx

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
