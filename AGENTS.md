# WebPatch development instructions

## Scope and safety

- Read `docs/design.md`, `README.md` and the latest stage evidence before changing implementation. Historical evidence describes the state at its recorded time; inspect current Git/CI state separately.
- Preserve separation between environment adapters, injectable system I/O, inventory/evidence models, vendor rules, planning, execution and verification. State unsupported capabilities explicitly.
- Scans are read-only. Never infer runtime safety from `php -v`, an empty inventory, a package version match, installation success, or unverified repository metadata. UNKNOWN must remain actionable and must block automatic repair.
- Do not modify the developer host's PHP, APT state, services or system packages. Dependencies belong in the project virtual environment. Installation/service tests belong in disposable Docker containers or GitHub-hosted Ubuntu VMs, with no host root/proc/socket mounts or privileged containers.
- Use no real vulnerability exploits in testing. Source risk rules from official PHP/Ubuntu/Debian advisories; record provenance, review time and expiry. Do not extend expiry without reviewing the source.

## Incremental delivery and Git commits

The user requires a Git commit after each independently verifiable stage of functionality.

1. State the stage's scope and acceptance criteria, implement it, then run the checks appropriate to that scope.
2. Preserve test logs/JUnit, relevant environment details and source/artifact hashes. Distinguish PASS, FAIL, NOT_RUN and BLOCKED. Never reuse old evidence as proof of the current code.
3. Review the diff and stage only changes belonging to the stage. Do not include virtual environments, caches, secrets or generated binary packages. Preserve unrelated user changes.
4. Make the stage commit autonomously once its acceptance checks pass; do not wait until several stages have accumulated. If a required gate is blocked, record that honestly and do not label the stage complete.
5. Every commit must include **Chinese and English** in both the subject and explanatory body. Example:

   ```text
   feat(phase-2a): 关联 PHP 服务与运行实例 / correlate PHP services and runtimes

   中文：说明问题、实现范围及未覆盖环境。
   English: Explain the problem, implemented scope and remaining limitations.

   验证 / Validation: Record the actual commands and results; link evidence paths.
   限制 / Limitations: Identify any unrun or blocked checks.
   ```

6. Report the commit hash and validation outcome after each stage. Push according to the current conversation's user authorization; never force-push or rewrite existing remote history as a routine step.

## Configuration autonomy

The user authorizes routine configuration needed for subsequent development, without repeated confirmation: project-local tooling and virtual environments, test/CI configuration, Git remote selection, and other reversible setup within this repository. Reuse the existing Git identity and authentication; do not expose credentials or modify unrelated global configuration.

Repository: `ninex98/webpatch`. Prefer the configured working origin; both HTTPS and SSH were reachable during setup on 2026-10-22. Verify current state rather than assuming an empty remote forever.

This permission does not turn development into authorization to repair the developer's host or other production systems. Runtime repair still requires the reviewed dry-run and explicit confirmation described in the design.
