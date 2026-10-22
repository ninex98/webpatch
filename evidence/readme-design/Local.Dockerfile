FROM webpatch-phase1:noble
COPY src /work/src
COPY scripts/build_deb.py /work/scripts/build_deb.py
COPY README.md LICENSE /work/
COPY docs/design.md /work/docs/design.md
RUN python3 scripts/build_deb.py && dpkg --install /work/dist/webpatch_0.1.0_all.deb
