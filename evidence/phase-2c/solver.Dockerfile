ARG BASE
FROM ${BASE}
COPY src /work/src
COPY apt_check.py /work/apt_check.py
ENV PYTHONPATH=/work/src PYTHONDONTWRITEBYTECODE=1
WORKDIR /tmp
