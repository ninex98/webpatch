# Context is assembled from the exact release artifact and its test harness.
ARG BASE=ubuntu:24.04
FROM ${BASE}
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1
RUN apt-get -o Acquire::Retries=3 update && apt-get install -y --no-install-recommends python3 curl ca-certificates
WORKDIR /work
COPY . /work
CMD ["python3", "tests/integration/installer_check.py"]
