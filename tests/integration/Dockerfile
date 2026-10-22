ARG BASE=ubuntu:24.04
FROM ${BASE}
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1
RUN apt-get update && apt-get install -y --no-install-recommends python3 php-fpm php-cli libapache2-mod-php ca-certificates
WORKDIR /work
COPY . /work
RUN python3 scripts/build_deb.py && apt-get install -y ./dist/webpatch_0.1.0_all.deb
RUN WEBPATCH_DISPOSABLE_CONTAINER=1 PYTHONPATH=src python3 tests/integration/package_control_check.py
CMD ["python3", "tests/integration/check.py"]
