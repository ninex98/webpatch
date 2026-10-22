FROM webpatch-phase1:noble
RUN apt-get update && apt-get install -y --no-install-recommends python3-venv git
WORKDIR /verify
COPY . /verify/webpatch
RUN cd webpatch && python3 -m venv .venv && .venv/bin/python -m pip install . && .venv/bin/webpatch --version
ENV PATH=/verify/webpatch/.venv/bin:$PATH
WORKDIR /verify/webpatch
