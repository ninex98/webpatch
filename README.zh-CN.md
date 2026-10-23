<p align="center">
  <picture>
    <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="assets/readme/hero-mobile-dark.svg">
    <source media="(max-width: 600px)" srcset="assets/readme/hero-mobile-light.svg">
    <source media="(prefers-color-scheme: dark)" srcset="assets/readme/hero-dark.svg">
    <img src="assets/readme/hero-light.svg" alt="WebPatch — Evidence before action. 只读 PHP 运行时安全清单。" width="100%">
  </picture>
</p>

<p align="center">
  <a href="https://github.com/ninex98/webpatch/actions/workflows/ci.yml"><img src="https://github.com/ninex98/webpatch/actions/workflows/ci.yml/badge.svg?branch=main" alt="main 分支 WebPatch 安全检查状态"></a>
  <a href="#roadmap"><img src="assets/readme/preview-badge.svg" alt="0.1.0 · 开发预览版"></a>
  <a href="LICENSE"><img src="assets/readme/license-badge.svg" alt="许可证：Apache-2.0"></a>
</p>

<p align="center">
  <a href="#quick-start">快速开始</a> · <a href="#cli-preview">预览</a> · <a href="docs/cli.md">CLI 参考</a> · <a href="README.md">English</a>
</p>

# WebPatch

**Evidence before action. 先有证据，再采取行动。** 一个审慎的 PHP 运行时安全 CLI：发现本地安装，依据厂商公告比对包版本，生成可供审阅的修复计划。

**0.1.0 为开发预览版。** 扫描保持只读；显式服务准备在精确计划 hash 确认后可以重启声明的服务。包修复要求完整受控证据及所审阅计划的精确 hash 确认。内置规则聚焦 PHP2Shell（`CVE-2026-109618` / `CVE-2026-109619`）；包版本符合修复边界，不等于正在运行的服务安全。

## 为什么选择 WebPatch

终端里的 PHP，未必是处理网站请求的 PHP。发行版可能将修复回移植到旧版本，而运行中的进程也可能仍持有更新前的映像。

WebPatch 关联**包、进程、服务与本地证据**，分别呈现版本判断、文件身份和运行时安全状态，并将缺失的证明明确标为 `UNKNOWN`。

<a id="quick-start"></a>

## 快速开始

在目标 Linux 系统上，准备好 **Git 和 Python 3.10+，且 `venv`、`pip` 可用**。从本仓库安装到虚拟环境；运行时无第三方 Python 依赖。

```sh
git clone https://github.com/ninex98/webpatch.git
cd webpatch
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/webpatch scan
```

扫描不需要 root，受限读取会成为覆盖缺口。发现潜在受影响包时退出码为 **1**，未知或覆盖不完整时为 **2**；二者均不代表安全检查通过。

导出证据并生成计划：

```sh
.venv/bin/webpatch scan --format json > scan.json
.venv/bin/webpatch plan --dry-run --format json > reviewed-plan.json
.venv/bin/webpatch verify-plan reviewed-plan.json --format json
```

本预览版的 `plan` 和 `verify-plan` 返回 **4**。这些诊断计划均为 `BLOCKED`、`executable=false`；APT 模拟通过也不授权任何变更。退出码、包缓存验证和本地 `.deb` 构建见 [CLI 参考](docs/cli.md)。目前没有公开 APT 仓库或 GitHub Release 安装入口。

<a id="cli-preview"></a>

## 命令行预览

<p align="center">
  <picture>
    <source media="(max-width: 600px)" srcset="assets/readme/terminal-mobile.svg">
    <img src="assets/readme/terminal.svg" alt="Ubuntu 24.04 容器内实际输出：作用域为 container，运行时安全为 UNKNOWN，计划为 BLOCKED，apply 拒绝执行。" width="100%">
  </picture>
</p>

于 **2026-10-22** 在隔离的 **Ubuntu 24.04 / arm64 容器**中，从已安装的 CLI 采集。图中节选真实输出，仅增加视觉换行；此容器输出 `APT dry-run: NOT_RUN`。终端外观是展示设计，并非内置 TUI。[完整文本与采集说明](assets/readme/README.md)。

诊断流程为**发现 → 判断 → 审阅**。独立的[受控维护流程](docs/cli.md#managed-package-repair)增加显式探针、经确认的服务准备、完整源码包组计划、持锁复核和修复后验证。内部原生矩阵已通过，刚开放的安装后 CLI 正在进行最终独立验收。

## 核心能力

- **本地运行时发现。** 关联 dpkg 包、进程身份、命名空间、systemd 单元、FPM pools 和静态 Web handler，并报告无法确认的关系。
- **尊重厂商修复策略。** 使用发行版专属规则和 `dpkg --compare-versions`，识别回移植修复，不直接比较上游版本字符串。
- **Ubuntu 与 Debian 归档身份检查。** 对支持的官方源验证已有 InRelease 签名、Packages 摘要、缓存 `.deb` 和受支持运行文件；证据缺失时保持未知。
- **真实 APT 模拟。** 针对认证的 Ubuntu/Debian 同 PHP 分支精确候选生成计划，列出依赖变化、可能的服务中断和阻断原因，不安装软件包。
- **独立扩展。** `scan-node` 覆盖两项已审阅的 Debian Node 运行时 CVE；`rebuild-plan` 提供容器重建建议，不构建或部署镜像。
- **可审阅的证据。** JSON 报告、输入摘要、有时效的计划与 `verify-plan` 漂移检查；绝不把已保存的计划数据当成命令执行。

## 兼容性

下表描述当前代码能力，不保证穷举发现。**不支持无人确认的修复；受控修复要求精确确认和全部门禁。**

| 环境 | 当前可用 | 边界 / 验证范围 |
| :--- | :--- | :--- |
| Ubuntu 22.04 / 24.04，官方 APT PHP | 发现、厂商版本对照、归档身份、主机 APT 模拟 | 仅官方直连源；托管 VM CI 覆盖 FPM 和 mod_php |
| Debian 12 / 13，官方 PHP 包 | 发现、厂商版本对照、归档身份、APT 模拟和受控准备 | 独立归档与 FPM/mod_php 内部修复测试在 Debian QEMU 客体通过；安装后 CLI 待验收 |
| Debian 12 / 13，官方 Node.js | 独立只读清单和两项运行时 CVE 规则 | 独立原生容器测试；无 npm 依赖审计或 Node 修复 |
| Ubuntu / Debian Docker 容器内部 | 当前容器清单、重建建议 | 不原地修复、不做 APT 模拟；Docker CI 覆盖 Ubuntu 22.04 / 24.04、Debian 12 |
| 从宿主机观察 Docker / containerd | 进程、命名空间和常见 socket 线索 | 不访问 daemon、不扫描镜像、不枚举容器集群 |
| PPA / Sury、混合源、ESM、不支持的镜像源 | 源审计、可读清单及阻断项 | 不支持的信任路径；不自动修复 |
| 自编译、`/usr/local`、`/opt/php`、宝塔 | 常见路径和进程线索 | 补丁状态未知；不穷举任意安装目录 |
| CGI、FrankenPHP、LiteSpeed、PHP 内置服务器 | 可观察时提供包或进程线索 | 运行时安全未知；无专用修复支持 |
| 其他操作系统、隐藏 PID、权限受限 | 可读观察结果和覆盖缺口 | 无受支持修复路径；macOS / Windows 未经扫描目标验证 |

## 安全设计

**观察，不改变目标。** 扫描不执行 PHP、不发送 HTTP 请求、不访问容器 daemon、不刷新 APT 索引、不安装包、不重启服务。APT 模拟使用独立临时配置，不执行系统 hooks，且仍将其列为阻断项。

**规则有出处、有时效。** [内置规则](src/webpatch/data/php2shell.json) 记录 PHP、Ubuntu、Debian 官方来源、修订号、审阅时间和有效期。审阅于 **2026-10-22**，有效至 **2026-10-29 00:00 UTC**。过期或系统时间早于审阅时间时，判断降为 `UNKNOWN`。没有自动在线规则更新；延长日期前必须重新审阅来源。

**未知必须可追踪、可阻断。** `MEETS_VENDOR_FIX` 仅为包版本比较，`VERIFIED_LOCAL_ASSOCIATION` 仅为本地关联检查，均不能证明已加载配置、应用路由或健康状态。所有报告保留 `safe=false`，未知证据阻断自动修复。摘要不等于远程证明，也不能证明遭 root 入侵的主机完整性。

**执行必须经过审阅。** 计划绑定规则、作用域和观察状态，最多 30 分钟有效，可再次检查漂移。移除、降级、新增依赖、跨分支及未批准的依赖变更均阻断自动路径。`apply` 仅接受审阅后的 schema 5 受控计划及其精确 hash，没有 `--yes` 绕过开关。精确 hash 确认、类型化包执行、修复后检查和哈希链失败审计已实现，限定于已认证的有限 profile；不承诺自动回滚。

## 文档

| 资源 | 内容 |
| :--- | :--- |
| [CLI 参考](docs/cli.md)（English） | 命令、退出码、报告语义和本地打包 |
| [架构与分阶段设计](docs/design.md) | 组件边界、威胁假设和验收门禁 |
| [开发状态与证据](docs/development-status.md)（中文 / English） | 对应源码的验收、保留的失败记录与待完成门禁 |
| [CI 工作流](.github/workflows/ci.yml) · [实时运行记录](https://github.com/ninex98/webpatch/actions) | 17 项：fixtures、包/Node/归档容器、四格 Ubuntu VM 和四格独立 Debian 客体 |
| [视觉资源与终端记录](assets/readme/README.md)（English） | 可编辑 SVG、采集出处和可访问的文本 |

历史证据仅对应所记录的源码版本。CI 徽章跟踪 `main`，不代表运行时安全或覆盖率承诺。

<a id="roadmap"></a>

## 路线图

- **已实现：** 清单、Ubuntu/Debian 归档认证、APT 模拟、显式探针、受控准备、精确修复审阅、类型化事务和修复后验证。
- **最终 CLI 验收待完成：** Ubuntu/Debian 内部升级/故障矩阵已 17/17 PASS，刚开放的安装后入口正在独立验证，见[当前状态](docs/development-status.md)。
- **独立扩展：** Node.js 运行时发现/规则和容器重建建议；自动镜像构建/发布、npm 修复及公开签名 APT 仓库不属于本次交付。

原设计四阶段范围见[分阶段设计](docs/design.md)。有限测试站点通过不等于任意生产站点认证。

## 参与贡献

请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md)（English）。新增适配器须明确能力边界，提供失败路径 fixtures 和真实环境证据。开发与安装测试使用项目虚拟环境、一次性容器及 GitHub 托管 VM。

## 许可证

[Apache License 2.0](LICENSE)。名称与本地 SVG 可独立于 CLI 调整；本次展示设计不改变既有许可证或发布策略。
