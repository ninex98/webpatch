# 阶段一验收记录

日期：2026-10-22（Asia/Shanghai）。范围：只读扫描、版本对照、阻断式规划、打包与隔离测试。没有实现或执行漏洞修复。

## 已通过

| 验证 | 结果 | 证据 |
|---|---|---|
| Python 3.10.19 / pytest 8.4.2 | 140 passed；54 种服务器 fixtures | [日志](pytest-python310.log)、[JUnit](pytest-python310.xml)、[依赖版本](python310-dependencies.txt) |
| Python 3.12 / pytest 9.1.1 | 140 passed | [日志](pytest-python312.log)、[JUnit](pytest-python312.xml) |
| 核心代码语句覆盖率 | 97.58%；不是修复正确性的证明 | [覆盖率数据](coverage.json) |
| Ubuntu 22.04 / Python 3.10 / arm64 Docker | PASS | [结果与源码摘要](docker-jammy-result.json)、[构建日志](docker-jammy-final-build.log)、[镜像身份](docker-jammy-image.json) |
| Ubuntu 24.04 / Python 3.12 / arm64 Docker | PASS | [结果与源码摘要](docker-noble-result.json)、[构建日志](docker-noble-final-build.log)、[镜像身份](docker-noble-image.json) |
| Debian 12 / Python 3.11 / arm64 Docker | PASS | [结果与源码摘要](docker-bookworm-result.json)、[构建日志](docker-bookworm-final-build.log)、[镜像身份](docker-bookworm-image.json) |
| VM 脚本防止宿主误执行 | 非 GitHub-hosted 环境在安装命令之前拒绝；bash 语法检查通过 | [拒绝日志](vm-host-refusal.log) |

每个 Docker 验证包含：构建 `.deb` 并通过 APT 安装；读取真实 CLI/FPM/mod_php 包；15 组独立预期值与原生 dpkg 比较；拒绝执行修复；核对包内没有 maintainer scripts；安装文件字节与源码相同；扫描前后 PHP/Apache/APT 配置、APT lists 和 dpkg status 内容摘要一致。运行参数为 `--read-only --network none --cap-drop ALL --security-opt no-new-privileges`，没有宿主挂载或 Docker socket 挂载。

最终三份结果中的全部运行时代码/规则 SHA256 已与当前源码逐一核对。版本规则摘要为 `f2fe32859700b27b380abc7212f8cab0d8dc6129a3e402f2489f4499c0c1e62d`。机器可读汇总见 [verification.json](verification.json)，源码/脚本/测试及制品摘要见 [source-manifest.json](source-manifest.json)。

生成的本地安装制品为 `dist/webpatch_0.1.0_all.deb`，SHA256：`d0f22bd9ab73b796ceb780c61e681412eda2a9412f7b86625e5c435140819b58`。这是未发布的本地预览构建，没有公开 apt 仓库。构建、安装、包/服务软件准备全部发生在容器内；宿主仅创建项目虚拟环境、项目文件和 Docker 测试镜像，未安装系统包或修改宿主 PHP/服务配置。

## 执行环境偏差与失败记录

- PyPI 官方下载遇到超时；项目 Python 3.10 虚拟环境通过清华 PyPI 镜像安装固定的 pytest/pytest-cov 版本后通过。详见 [安装日志](dependency-install.log)。没有修改其他项目或系统 Python 的依赖。Python 3.12 检查复用了已有解释器，禁用自动 pytest 插件加载。
- 最初的 Python 3.12 检查为 135 项；随后增加资源限额、架构身份和规则接口检查，最终两个解释器都是 140 项。中间尝试在旧环境加载未安装的 coverage 插件失败，保留 [失败日志](pytest-bootstrap-coverage-unavailable.log)，不计为通过证据。
- Debian 官方基础镜像下载缓慢，取消了该次构建，改用本机已有的 `docker.m.daocloud.io/library/python:3.11-slim-bookworm` 基础镜像。真实 OS 经扫描确认为 Debian 12；PHP 包仍从 Debian 官方 APT 源安装。一次包下载 HTTP 502 导致失败，重试后通过；[失败日志](docker-bookworm-cached-base-build.log) 保留。
- Ubuntu 24.04 官方 ports 源反复下载超时，取消首次构建。只在测试容器中换用清华 ubuntu-ports 镜像；保留原 Ubuntu 签名信任链，没有 `trusted=yes` 或禁用校验选项。[完整替代 Dockerfile](Dockerfile.noble-mirror)、[首次取消日志](docker-noble-build.log) 和最终构建日志均保留。CI 默认仍使用标准 Dockerfile 和发行版默认源。

## 明确未验证

GitHub Actions 临时 VM **NOT_RUN**：项目尚未配置 Git 仓库/远程地址，没有触发云端工作流。已准备 Ubuntu 22.04/24.04 × FPM/mod_php 四格矩阵；仍需真实运行，才能声称 amd64 和 systemd 安装/服务级验证通过。工作流使用独立 `ci-evidence/`，防止上传本目录的历史结果冒充当前结果；显式 bash pipefail 避免 tee 掩盖失败。

Docker 不提供此处所需的 systemd 生命周期验证。阶段一没有验证软件源与二进制的密码学身份、完整站点路由、进程加载补丁、真实 APT 修复模拟或修复后健康状态。因此所有运行时状态仍为 UNKNOWN，所有计划不可执行；没有任何“已安全”结果。

[CLI 新、FPM 旧的示例报告](example-mixed-sapi-report.json) 和 [阻断式计划](example-blocked-plan.json) 均由 synthetic fixtures 生成，不是宿主机扫描结果。
