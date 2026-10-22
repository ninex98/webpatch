# CLI reference

WebPatch 0.1.0 requires Python 3.10+. Commands below assume the source installation in the [README](../README.md); an installed `.deb` also exposes `webpatch` on `PATH`.

## Read-only inventory

```sh
.venv/bin/webpatch --help
.venv/bin/webpatch --version
.venv/bin/webpatch scan
.venv/bin/webpatch scan --format json
```

Run on the target system without root. `scan` does not execute PHP, probe websites or access container daemons. Restricted reads are coverage gaps, not evidence of absence. Container scans apply only to that container's scope.

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

There is no `--yes` bypass or enabled package installation / upgrade path. The transaction state machine remains behind unresolved admission gates. Explicit service preparation below has a separate, exact-hash confirmation boundary.

## Explicit evidence and controlled service preparation

`deployment-manifest` and `verify-deployment` reconcile declared observations without claiming exhaustive coverage. `audit-consumers --target-package NAME:ARCH` checks all visible process images/mappings. `review-maintenance --dry-run` reads authenticated old/new control archives without running scripts. All retain blocked package-execution semantics.

`probe-template` prints the shipped PHP collector; it never deploys it. A separately root-deployed, uncached collector can be queried only through an explicit `probe-application --url http://127.0.0.1:PORT/collector.php --script /var/www/.../collector.php --service UNIT`. The kernel callback binds a response to a process; ordinary HTTP markers do not. The standalone receipt lasts at most five minutes.

Controlled preparation is a **service-changing operation** for supported Ubuntu FPM/mod_php profiles. It copies reviewed server configuration into private local snapshots, installs authenticated temporary runtime service definitions, restarts the named services, and verifies their read-only configuration views and explicit probes. Requests may be interrupted. It does not install packages or edit canonical configuration values. Dynamic code hooks, unknown modules, untrusted service definitions and unstable ondemand pool profiles are unsupported.

Create a probes JSON list with one declaration per FPM pool (Apache uses `pool_listener: null`):

```json
[{"service":"php8.1-fpm.service","url":"http://127.0.0.1:18080/webpatch-proof.php","script":"/var/www/html/webpatch-proof.php","pool_listener":"/run/php/php8.1-fpm.sock"}]
```

Generate and review the complete preparation plan and its interruption notice, then confirm that exact document digest:

```sh
webpatch prepare-plan --service php8.1-fpm.service --probes probes.json --package-cache /path/to/cache --format json > preparation.json
sudo webpatch prepare-scope preparation.json --confirm-sha256 REVIEWED_PREPARATION_SHA256
```

`prepare-plan` returns 4; it does not mutate services. Successful `prepare-scope` returns 0 with a locally authenticated receipt; blocked or partial preparation returns 4. Snapshot inputs and process identities are rechecked; the receipt is not root-compromise attestation or package-repair authorization. Private snapshot files contain the copied configuration values and remain under a protected local state directory; exported receipts contain hashes and paths, not these values or the signing key. Controlled snapshot receipts can last up to 30 minutes, bounded by all dependent evidence.

`retire-preparation SIGNED_RECEIPT.json --confirm-sha256 RECEIPT_DOCUMENT_SHA256` removes only unchanged runtime definitions owned by that receipt and reloads the manager. It does not restart services: current read-only views remain active until their processes exit, while future starts use canonical service configuration. Use `--state-directory` when preparation used a non-default state directory. See [phase-three contracts](phase-3.md) for the supported boundaries and recovery semantics.

## Exit codes

| Code | Meaning |
| :--- | :--- |
| `0` | Successful help / version / template or explicitly confirmed service preparation; current scans never return 0 |
| `1` | At least one observed package version is below a matched vendor fix boundary |
| `2` | Unknown / incomplete coverage; argparse also uses 2 for usage errors, so inspect stderr |
| `3` | The scan could not finish, for example because rule data is invalid |
| `4` | Diagnostic plans/reviews, blocked execution, or blocked/partial service preparation; inspect JSON status |

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

## Independent runtime and container extensions

`webpatch scan-node --format json` discovers Node packages/processes without running Node or npm. The separately dated rules cover two reviewed runtime CVEs for Debian 12/13; unsupported vendor/version families remain UNKNOWN. This does not audit npm dependencies or enable Node repair.

Inside the target container, `webpatch rebuild-plan --image registry.example/team/php@sha256:<64-hex-digest> --format json` returns scoped image rebuild guidance (exit 4). The image reference is declared, not authenticated by the scan. It does not build, push, roll out or install packages in place. See [extension boundaries and evidence](phase-4.md).
