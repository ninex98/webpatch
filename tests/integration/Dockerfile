ARG BASE=ubuntu:24.04
FROM ${BASE}
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1
RUN apt-get update && apt-get install -y --no-install-recommends python3 php-fpm php-cli libapache2-mod-php ca-certificates
WORKDIR /work
COPY . /work
# Ubuntu's minimal image filters /usr/share/doc; include this package's docs
# explicitly so the fixture can verify their installed bytes too.
RUN python3 scripts/build_deb.py && apt-get -o 'DPkg::Options::=--path-include=/usr/share/doc/webpatch/*' install -y ./dist/webpatch_0.1.0_all.deb
CMD ["python3", "tests/integration/check.py"]
