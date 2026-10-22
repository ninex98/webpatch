# README presentation stage / README 展示阶段

**PASS — documentation and visual presentation accepted locally, 2026-10-22.** / **PASS — 双语文档与视觉展示已完成本地验收，2026-10-22。**

Scope: English and Chinese READMEs, an original editable SVG identity, responsive hero / terminal artwork, CLI reference and contributor guide. Application code, rules, architecture, build scripts, CI configuration and license are unchanged. / 范围：双语 README、原创可编辑 SVG 标识、响应式 Hero 与终端图、CLI 和贡献指南；业务代码、规则、架构、打包脚本、CI 与许可证均未修改。

Baseline: `7495d77c1835c519ca0f487a0372064e998e02de`. At task start, phase-2C acceptance files were already modified by another task; that task committed them as this baseline while README work proceeded. A subsequent independent planning-document commit, `596724e`, also preceded this stage commit. Neither is part of this stage. / 开始时已有其他任务的阶段 2C 验收改动，期间由该任务独立提交；本阶段未包含那些改动。

## Acceptance / 验收

| Check | Status | Evidence / boundary |
| :--- | :--- | :--- |
| Capability / CLI / packaging / tests / CI / design audit | PASS | Compared actual modules, parser, tests, package builder and workflow; no speculative install channels or runtime guarantees |
| English / Chinese parity | PASS | Same shell blocks, inline technical identifiers and image sources; manually compared all feature, support, security and roadmap statements |
| Current fixture suite | PASS | [pytest.log](pytest.log), [JUnit](pytest.xml): 243 tests on Python 3.10.19; no new business tests needed for this documentation stage |
| Clean source install on developer platform | PASS | [source-install.log](source-install.log): project-local temporary venv, built wheel, version / help checked; no host PHP or package changes |
| Linux source install | PASS | [linux-source-install.log](linux-source-install.log), [source CLI capture](cli/source-install-capture.json): Python 3.12, Ubuntu 24.04 arm64, project venv, real CLI exits 0 / 2 / 2 / 4 / 4 / 4 / 4 |
| Public Git clone URL | PASS | [clone-url.log](clone-url.log): HTTPS `git ls-remote` resolved the actual public repository; no release exists at verification time |
| Standard Dockerfile fresh build attempt | BLOCKED | [docker-build.log](docker-build.log): Docker Hub metadata request timed out (command failed); not counted as a successful build |
| Existing local Ubuntu base + current `.deb` | PASS | [Local.Dockerfile](Local.Dockerfile), [build log](docker-local-build.log), [image identity](container-image.json); rebuilt and installed current source in a disposable container |
| Installed package integration | PASS | [container-check.json](container-check.json): real dpkg comparisons, installed/source byte equality, expected scopes/exits and unchanged APT/dpkg/configuration state |
| Actual CLI artwork | PASS | [full capture](cli/capture.json), [capture script](cli/capture.py), [accessible transcript](../../assets/readme/cli-transcript.txt); UID/GID 65534, no fake system reader, stdout/stderr preserved |
| GitHub-flavored Markdown | PASS | [render log](markdown-render.log): GitHub `/markdown` API accepted five Markdown documents including native picture/source markup |
| SVG / link / anchor checks | PASS | [validation.log](validation.log), [HTTP results](links.json): 9 SVGs, 84 local/external link references checked across 5 documents, 7 unique external URLs returned 200 |
| Desktop / mobile / themes | PASS | [browser-qa.json](browser-qa.json): English + Chinese × light + dark × 320 / 390 / 1280 px; all images loaded and no page-width overflow; [SVG bounds](svg-bounds.json) confirm no clipped text |
| Asset reproducibility | PASS | Standard-library [generator](../../assets/readme/generate.py) produces identical SVG bytes from the saved capture |
| Recorded source-baseline CI | PASS | [ci-baseline.json](ci-baseline.json): Actions run 39752379977 passed on baseline `7495d77`; historical context, not evidence of the subsequent documentation commit; [current CI snapshot](ci-current.json) is recorded separately |
| CI for this documentation commit | NOT_RUN | No push was requested; no remote gate is required for this documentation-only stage |
| Real repair / upgrade / service restart / post-repair health | NOT_RUN | Outside this task; the preview still refuses execution |

## Reproduction / 复现

Run from the repository root with the existing project Python 3.10+ environment:

```sh
.venv/bin/python -m pytest --junitxml=evidence/readme-design/pytest.xml
.venv/bin/python assets/readme/generate.py
.venv/bin/python evidence/readme-design/checks.py
```

The checks script validates local links/anchors, SVG structure, bilingual technical parity, capture semantics, deterministic generation and live HTTP URLs. It is a documentation check, not application test coverage. The rendering helper uses `gh api markdown`, writes disposable HTML to `build/readme-preview/`, and uses a local CSS approximation of GitHub solely for visual QA. No CSS or JavaScript is embedded in the delivered Markdown or required by the README. GitHub's renderer does not assign generated heading IDs through the API; the preview helper adds them for local navigation. Actual custom Chinese anchors are preserved by GitHub sanitization.

Visual QA used the in-app browser at the three recorded widths. Dark variants were selected in explicit dark preview shells, without changing system appearance. Native light/mobile `picture` selection was also checked via loaded image URLs. Screenshots were visually reviewed and remain in ignored `build/readme-preview/`; their hashes are recorded in the manifest. This is GitHub-rendered Markdown in a local preview, not a claim that the unpushed commit has been viewed on the hosted repository.

The terminal SVGs show exact selected lines with visual wrapping and explicit omission labels. The container has installed PHP packages but does not demonstrate a running FPM service or healthy website. Its APT simulation is `NOT_RUN`; saved-plan verification retains `PLAN_SIMULATION_DRIFT`. These are expected blocked observations, not a successful host simulation or repair. The reference CI evidence separately covers host APT simulation.

The standard registry-based build was blocked by external availability. The fallback used an existing local Ubuntu test image with current source copied in, and the independent Linux venv installation used [Source.Dockerfile](Source.Dockerfile). Installation happened only inside disposable containers. Runtime captures used `--read-only --network none --cap-drop ALL --security-opt no-new-privileges`, a 64 MB `/tmp` tmpfs for the saved plan and no host mounts. Source installation setup had network access to obtain venv tooling / build dependencies; captures did not.

The local previews and support files were assembled before final validation: a missing evidence README link was filled in, the inline-code parity regex was corrected to exclude fenced blocks, long mobile navigation was shortened, and the mobile terminal was given a narrower viewBox. Final checks were rerun after these corrections.

[manifest.json](manifest.json) records environment, source, documentation, asset and evidence hashes. The Linux install log has CR progress output normalized to LF for Git; its original byte hash is also retained. No venv, cache, credentials, wheel or `.deb` binary is committed. / manifest 记录环境及源码、文档、资源和证据摘要；未提交虚拟环境、缓存、凭据或二进制包。
