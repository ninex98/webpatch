# 阶段 5A：Linux 一键安装与版本分发 / Linux installation and versioned distribution

日期 / Date: 2026-10-23 (Asia/Shanghai). **本地验收 PASS，远端 CI_PENDING；公开 Release / 真实 GitHub 下载 NOT_RUN。** 此为可审阅的 CI-pending checkpoint，不宣布公开安装交付完成。基于 `be8c85c3503a6bc362b9a5c1379f0d242a212f36` 的独立阶段，实际工作树源码/制品摘要见 `manifest.json`，不是旧 17/17 CI 的复用。

## 范围和验收 / Scope and acceptance

- 单一程序版本 `webpatch.__version__` 驱动 Python 元数据、CLI、Debian 包名/control 及现有 CI 包路径；首个待发布版本 0.1.0。
- Ubuntu 22.04/24.04、Debian 12/13 一键安装；严格解析固定版本/最新 Release URL、HTTPS、SHA256、包名/版本/架构；APT 仅安装工具及必要依赖，不自动刷新索引、添加源、扫描或修复 PHP。其他系统及降级请求拒绝。
- GitHub distribution workflow 先构建一次制品，再安装同一制品四格。默认只产生 CI artifacts；手动 opt-in 才创建草稿，要求 main 精确 SHA 的 safety CI 成功及版本标签尚不存在。公开发布仍为独立动作。
- 验收包括 fixtures、wheel/sdist 构建、shell/workflow 静态检查、真实容器安装/重装/升级和故障拒绝；不修改开发宿主 PHP/APT/服务/系统包。

## 实际结果 / Actual results

| 检查 | 结果及证据 |
|---|---|
| `.venv/bin/python -m pytest --junitxml=evidence/phase-5a-installation/pytest.xml` | **PASS**, 617 passed; `pytest.log`, `pytest.xml` |
| `.venv/bin/python -m build --no-isolation --outdir dist/python` | **PASS**, wheel/sdist; `python-build-final.log`; 本地工具仅安装到 `.venv` |
| shell syntax / diff whitespace / YAML / actionlint 1.7.12 | **PASS**, `validation.log`, `actionlint.log`; actionlint 的 shellcheck 集成未启用 |
| Ubuntu 22.04 / 24.04、Debian 12 / 13，arm64 | **PASS**, 同一 `.deb` 每格 21 场景；`*-exact-result.json`、`*-exact-build.log`、`*-exact-test.log`、`environment.json` |
| Release `.deb` 中全部实现/规则/探针及包内文档对比当前工作树 | **PASS**, 字节一致；`validation.log` |
| tag/version mismatch | **PASS**, `scripts/release_assets.py --tag v99.0.0` 返回 2，拒绝错误标签 |
| 本次源码的 hosted amd64 安装及完整 17-job safety CI | **NOT_RUN / CI_PENDING**, 尚未推送 |
| 公开 Release、真实 GitHub 下载、交互式 sudo 认证、缺少 Python 时在线拉取依赖 | **NOT_RUN**；不伪装为容器验证结果 |

同一制品 SHA256：`e203caefd110255c3e0483a12bc5b0c1d008fc3e2633b616cf016b6c7f9f06a9`。21 个场景包括参数错误、其他 OS/发行版、下载失败、最新 URL 异常、缺失/重复/坏 checksum、篡改包、包名/版本/架构错误、APT 失败、首次安装、重装、真实旧包升级、降级拒绝，以及已安装 CLI 空清单仍为 UNKNOWN/safe=false 的只读扫描。成功路径使用真实 APT/dpkg；只有 GitHub 下载传输由本地离线 release fixture 替代。

精确制品测试命令：`docker build -f tests/integration/Release.Dockerfile --build-arg BASE=<base> -t webpatch-exact-release:<label> ci-evidence/distribution-context`，然后 `docker run --rm --network none --security-opt no-new-privileges webpatch-exact-release:<label>`。context 由同一 `dist/release`、源码版本声明和 test harness 组成，与 workflow 做法一致。镜像构建阶段允许下载 OS 测试依赖；测试执行禁网。容器无 privileged、宿主 root/proc/socket 挂载或宿主系统更改。

## 保留失败 / Retained failures

- `noble-build.log`: Ubuntu 官方 ports 源曾返回 HTTP 502，容器构建 **FAIL**。重试仍保留签名校验，未使用不可信源/跳过验证；后续镜像构建及四格验收通过。
- `noble-test.log`: 安装测试最初套用只读扫描容器的 `--cap-drop ALL`，导致 APT 不能切换 `_apt` uid/gid，**FAIL**。只调整 disposable 安装测试的容器能力为普通 Docker 默认值，保留禁网/no-new-privileges；不放宽产品安全门禁、不运行 privileged。

未加入二进制包、venv、缓存或秘密。`dist/` 与测试 context 保持忽略；Git 中保留日志/JUnit、环境/源码和制品哈希。安装可移植性不扩张已认证的 amd64 修复 profiles；规则仍在 2026-10-29 00:00 UTC 到期。
