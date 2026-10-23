# WebPatch

**Find PHP runtime risks. Review the evidence. Confirm the repair.** Scans are read-only; missing evidence stays `UNKNOWN`.

<p>
  <a href="https://github.com/ninex98/webpatch/releases/tag/v0.2.0"><img src="assets/readme/preview-badge.svg" alt="0.2.0 · Linux preview"></a>
  <a href="https://github.com/ninex98/webpatch/actions/workflows/ci.yml"><img src="https://github.com/ninex98/webpatch/actions/workflows/ci.yml/badge.svg?branch=main" alt="Safety checks on main"></a>
  <a href="LICENSE"><img src="assets/readme/license-badge.svg" alt="Apache-2.0"></a>
</p>

[Install](#quick-start) · [CLI Preview](#cli-preview) · [Commands](#commands) · [简体中文](README.zh-CN.md)

<a id="quick-start"></a>

## One-command install / upgrade

**Ubuntu 22.04 / 24.04 · Debian 12 / 13** — copy and run:

```sh
(wp_tmp=$(mktemp -d) && trap 'rm -rf "$wp_tmp"' EXIT && curl -fsSL --retry 5 --retry-all-errors --retry-max-time 180 --connect-timeout 15 --max-time 60 --proto '=https' --proto-redir '=https' --tlsv1.2 https://github.com/ninex98/webpatch/releases/latest/download/install.sh -o "$wp_tmp/install.sh" && sh "$wp_tmp/install.sh" && /usr/bin/webpatch --version)
```

Requires `curl` and root/sudo. No Git, venv or pip. Downloads finish before execution; failures stop installation. [Download problems, pinned versions and uninstall →](docs/installation.md)

<a id="cli-preview"></a>

## CLI Preview

After installation:

```sh
webpatch scan
```

<picture>
  <source media="(max-width: 600px)" srcset="assets/readme/terminal-mobile.svg">
  <img src="assets/readme/terminal.svg" alt="Actual WebPatch output with a clear result, remaining checks and next step." width="100%">
</picture>

Actual 0.2.0 output in Ubuntu 24.04 / arm64. This empty inventory stays `UNKNOWN`. [Full capture](assets/readme/README.md).

<a id="commands"></a>

## Everyday commands

| Command | Effect |
| :--- | :--- |
| `webpatch scan` | Shows PHP findings, missing evidence and the next step |
| `webpatch scan --details` | Expands the evidence and coverage checks |
| `webpatch plan` | Previews candidate upgrades and blockers; installs nothing |
| `webpatch fix --dry-run` | Checks repair prerequisites without changing the system |
| `sudo webpatch fix` | Guides review and exact confirmation; may update packages or restart services |
| `webpatch scan-node` | Checks supported Node.js runtime rules; no npm audit or Node repair |
| `webpatch --version` | Shows the version actually being invoked |
| `webpatch --help` | Lists commands; use `webpatch fix --help` for repair options |

Only confirmed `fix` operations can change services/packages among these commands. It manages review files and recovery records. Repairs require supported official packages, authenticated archives and predeployed verification probes; unresolved conditions block execution.

`UNKNOWN` means incomplete evidence, `BLOCKED` means the current step cannot proceed, and `PARTIAL` means changes may already exist. [Result meanings, exit codes and JSON export →](docs/cli.md#reading-results)

## Support and boundaries

- **PHP repair:** official amd64 packages on Ubuntu 22.04/24.04 and Debian 12/13, supported FPM/mod_php profiles, same-branch changes after exact confirmation.
- **Containers and Node.js:** read-only inventory and container rebuild advice; no in-place container repair or automatic image deployment.
- **Other environments:** PPA/Sury/ESM, custom builds, unsupported architectures and macOS/Windows have no certified repair path. No automatic rollback or global safety guarantee.

PHP rules currently focus on PHP2Shell (`CVE-2026-109618` / `CVE-2026-109619`). Bundled rules expire **2026-10-29 00:00 UTC**; expired rules remain `UNKNOWN` until a source-reviewed update. [Detailed capabilities and validation →](docs/development-status.md)

## Documentation

[Installation & troubleshooting](docs/installation.md) · [CLI reference](docs/cli.md) · [Design](docs/design.md) · [Validation evidence](evidence/phase-6c-release/README.md)

[Contributing](CONTRIBUTING.md) · [Apache-2.0 license](LICENSE)
