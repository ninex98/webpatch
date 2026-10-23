ARG BASE=ubuntu:24.04
FROM ${BASE}
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get -o Acquire::Retries=3 update && apt-get -o Acquire::Retries=3 install -y --no-install-recommends curl ca-certificates sudo \
    && useradd --create-home --shell /bin/bash webpatch-test \
    && printf '%s\n' 'webpatch-test ALL=(root) NOPASSWD: /usr/bin/apt-get' > /etc/sudoers.d/webpatch-test \
    && chmod 0440 /etc/sudoers.d/webpatch-test \
    && test ! -x /usr/bin/python3
COPY verify.sh /verify.sh
USER webpatch-test
WORKDIR /home/webpatch-test
CMD ["bash", "/verify.sh"]
