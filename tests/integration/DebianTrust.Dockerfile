ARG BASE=debian:12
FROM ${BASE}
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1
RUN apt-get update && apt-get install -y --no-install-recommends python3 php-fpm php-cli gpgv ca-certificates
RUN mkdir /cache && cd /cache && apt-get download $(dpkg-query -W -f='${binary:Package}=${Version}\n' 'php[0-9]*-fpm')
WORKDIR /work
COPY . /work
CMD ["python3", "tests/integration/debian_trust_check.py"]
