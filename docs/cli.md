# CLI reference

WebPatch 0.1.0 requires Python 3.10+. Commands below assume the source installation in the [README](../README.md); an installed `.deb` also exposes `webpatch` on `PATH`.

## Read-only inventory

```sh
.venv/bin/webpatch --help
.venv/bin/webpatch --version
.venv/bin/webpatch scan
.venv/bin/webpatch scan --format json
```

Run on the target system without root. WebPatch does not execute PHP, probe websites or access container daemons. Restricted reads are coverage gaps, not evidence of absence. Container scans apply only to that container's scope.

The text view shows environment, rule revision, package assessments and structured coverage requirements. JSON (`schema_version=2`) also includes package versions, runtime files and mappings, observed UNIX listeners, static configuration relationships, source audit, package trust, references and evidence digests. Legacy `coverage_gaps` strings remain available. Each structured check names its subjects, evidence, reason and next verification step; `VERIFIED` describes only that specific relationship. `OBSERVED`, `UNKNOWN`, `UNSUPPORTED` and `NOT_CHECKED` cannot authorize repair.

| Field / value | Interpretation |
| :--- | :--- |
| `BELOW_VENDOR_FIX` | Observed package metadata is below the matched vendor boundary; potentially affected |
| `MEETS_VENDOR_FIX` | Package metadata meets that boundary; does not authenticate the package or running service |
| `UNKNOWN` | Evidence, rule coverage or runtime verification is incomplete |
| `VERIFIED_LOCAL_ASSOCIATION` | Local process / file / package / service relationship is consistent; not application health |
| `safe=false` | Retained in every current report; WebPatch does not certify runtime safety |

Report paths and package names can contain operational information. Process environments, full configuration contents and repository credentials are not included. Review reports before sharing.

## Verify existing package archives

```sh
.venv/bin/webpatch scan --package-cache /var/cache/apt/archives --format json
```

The default cache is `/var/cache/apt/archives`; use another absolute directory only if archives have already been obtained there. WebPatch never downloads them. The supported chain is existing Ubuntu InRelease signature → Packages digest and length → `.deb` digest and length → control identity → supported regular runtime files under `usr/bin`, `usr/sbin` and `usr/lib`.

Authentication currently covers direct official Ubuntu 22.04 / 24.04 sources with a pinned Ubuntu signing fingerprint. Missing archives, stale or damaged indexes, unsupported mirror lists, third-party / mixed sources and unknown identities remain blockers. Debian currently has vendor-version comparisons, not this archive authentication chain. File identity does not prove historical installation origin, maintainer scripts or memory integrity.

## Prepare and recheck a plan

```sh
.venv/bin/webpatch plan --dry-run --format json > reviewed-plan.json
.venv/bin/webpatch verify-plan reviewed-plan.json --format json
```

`plan` requires `--dry-run`. On supported Ubuntu hosts, authenticated same-branch targets can reach real `apt-get --simulate --no-remove --only-upgrade`. The simulator uses isolated temporary APT configuration, retains relevant system inputs, does not run system hooks, and does not refresh indexes, download or install. Special configuration and hooks still appear as blockers. Containers receive rebuild recommendations and do not enter APT simulation.

Plan schema 4 includes exact targets, dependency changes, complete observed scope, shared-package impact, individual review gates, service-interruption notes, input bindings, hashes and blockers. `apt_simulation` is `PASS`, `FAIL` or `NOT_RUN`; `PASS` does not mean the plan is executable. `READY_FOR_REVIEW` describes diagnostic readiness; execution admission stays `BLOCKED`. All plans remain `BLOCKED`, `executable=false`, with no executable actions. Removal, downgrade, new dependencies, cross-branch / release changes and untrusted or unapproved dependency changes block the automatic path.

Plans bind rules, host / boot scope, packages, configuration, repositories, indexes and observed runtimes. They expire within 30 minutes of both scan and generation, and no later than the rules or authenticated index validity. `verify-plan` rescans, repeats applicable simulation and compares saved data and gate decisions for drift; it never executes commands from the file. Saved schema 2/3 plans require a fresh scan and schema 4 plan (`PLAN_SCHEMA_RESCAN_REQUIRED`). Plan files have a separate 16 MiB read limit; ordinary configuration/procfs reads remain limited to 1 MiB. APT simulation does not hold a system lock, so rechecking is an observation, not a concurrency guarantee or authorization to execute.

To select packages, repeat `--target-package` with exact binary package and architecture IDs:

```sh
.venv/bin/webpatch plan --dry-run --target-package php8.1-fpm:amd64 --format json
```

Selection does not narrow discovery or hide other consumers of the same package. Unresolved instances remain visible and blocking. Static pool/handler matches and a process-owned listening socket do not prove loaded configuration or request attribution. See [the 2D contracts and boundaries](phase-2d.md) and [current-source acceptance evidence](../evidence/phase-2d4/README.md).

```sh
.venv/bin/webpatch apply
# stderr: BLOCKED: repair execution is disabled. No changes performed.
# exit: 4
```

There is no `--yes` bypass, executor, installation / upgrade action or rollback implementation. Future execution must confirm the exact reviewed plan hash, revalidate inputs and verify services and application health afterward.

## Exit codes

| Code | Meaning |
| :--- | :--- |
| `0` | Successful help / version operations; current scans never return 0 |
| `1` | At least one observed package version is below a matched vendor fix boundary |
| `2` | Unknown / incomplete coverage; argparse also uses 2 for usage errors, so inspect stderr |
| `3` | The scan could not finish, for example because rule data is invalid |
| `4` | Plan, plan verification or execution is blocked |

Do not chain expected nonzero scan / plan commands with `&&` or treat them as success in `set -e` scripts. JSON redirection writes the report even when the command returns 1, 2 or 4; handle these codes explicitly in automation. An empty inventory, installation success or matching version never establishes safety.

## Build a local Debian package

No public APT repository or GitHub Release is published. To build and test locally, run from the checkout with Docker available:

```sh
docker build -f tests/integration/Dockerfile --build-arg BASE=ubuntu:24.04 -t webpatch-test:noble .
docker run --rm --read-only --network none --cap-drop ALL --security-opt no-new-privileges webpatch-test:noble
```

The Dockerfile builds `/work/dist/webpatch_0.1.0_all.deb` and installs it **inside the disposable container**. The builder, `python3 scripts/build_deb.py`, runs only on Linux and only builds a package; it does not install it. The package depends on Python 3.10+ and dpkg, and has no maintainer scripts, daemon or third-party Python runtime dependencies. Build dependencies require network access; the test container runs without networking or host mounts.

To copy the locally built artifact out without mounting the host:

```sh
mkdir -p dist
container_id=$(docker create webpatch-test:noble)
docker cp "$container_id:/work/dist/webpatch_0.1.0_all.deb" dist/
docker rm "$container_id"
```

Only on an intended disposable Ubuntu / Debian test target, after copying that artifact into its current directory:

```sh
sudo apt install ./webpatch_0.1.0_all.deb
webpatch scan
```

Do not use installation or service tests to modify the developer host. See [CONTRIBUTING.md](../CONTRIBUTING.md) and the [design](design.md) for validation boundaries.
