# Contributing to WebPatch

Read the [README](README.md), [architecture and staged design](docs/design.md), [development instructions](AGENTS.md) and [current development status and linked evidence](docs/development-status.md) before changing implementation. Historical evidence applies to its recorded source revision; check current Git and CI separately.

## Local checks

Use Python 3.10+ with venv / pip support, inside the checkout:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m pytest --junitxml=evidence/pytest.xml
```

Do not modify the developer host's PHP, package manager or services. Use the [container instructions](docs/cli.md#build-a-local-debian-package) for packaging and integration checks. Service installation tests belong in disposable Docker containers or GitHub-hosted Ubuntu VMs and their disposable Debian QEMU guests, with no privileged mode or host root, `/proc` or socket mounts. Never run `scripts/ci_vm_smoke.sh` on a developer workstation or self-hosted runner.

## Changes we can evaluate

- Keep adapters, injectable system I/O, evidence models, vendor rules, planning, execution and verification separate.
- State discovery, assessment, planning and execution capabilities explicitly. New adapters need failure-path fixtures and relevant real environment validation.
- Preserve `UNKNOWN` and blocking behavior. Missing inventory, `php -v`, package-version matches and installation success are never proof of runtime safety.
- Source risk rules from official PHP / Ubuntu / Debian advisories, retaining provenance, review time and expiry. Re-review sources before extending validity. Do not use vulnerability exploits in tests.
- Keep [English](README.md) and [Chinese](README.zh-CN.md) capability descriptions aligned. Visual updates must retain actual CLI output and support GitHub Markdown without scripts, custom CSS or remote fonts.

## Evidence and commits

Define each stage's scope and acceptance checks before implementation. Record commands, environment details, logs / JUnit and source / artifact hashes, distinguishing `PASS`, `FAIL`, `NOT_RUN` and `BLOCKED`. Never use old evidence to certify changed code.

Review and commit each independently verified stage with Chinese **and** English in both the subject and explanatory body, following [AGENTS.md](AGENTS.md). Preserve unrelated changes; exclude environments, caches, secrets and generated binary packages. A required CI gate that has not run is pending, not passed.

Use [GitHub issues](https://github.com/ninex98/webpatch/issues) for reproducible bugs and scoped proposals. Include the version, environment and expected versus actual behavior; review reports for operational information before posting. Do not include credentials or private server data.
