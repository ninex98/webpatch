ARG BASE=debian:12
FROM ${BASE}
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1
RUN apt-get update && apt-get install -y --no-install-recommends python3 nodejs ca-certificates
WORKDIR /work
COPY . /work
RUN python3 scripts/build_deb.py && apt-get install -y ./dist/webpatch_$(python3 scripts/package_version.py)_all.deb
CMD ["python3", "tests/integration/node_check.py"]
