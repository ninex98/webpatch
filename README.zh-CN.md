# WebPatch

**发现 PHP 运行时风险，核实证据，再确认修复。** 扫描只读，证据不足时明确显示 `UNKNOWN`。

<p>
  <a href="https://github.com/ninex98/webpatch/releases/tag/v0.2.0"><img src="assets/readme/preview-badge.svg" alt="0.2.0 · Linux preview"></a>
  <a href="https://github.com/ninex98/webpatch/actions/workflows/ci.yml"><img src="https://github.com/ninex98/webpatch/actions/workflows/ci.yml/badge.svg?branch=main" alt="Safety checks on main"></a>
  <a href="LICENSE"><img src="assets/readme/license-badge.svg" alt="Apache-2.0"></a>
</p>

[安装升级](#quick-start) · [CLI 预览](#cli-preview) · [常用命令](#commands) · [English](README.md)

<a id="quick-start"></a>

## 一键安装 / 升级

**Ubuntu 22.04 / 24.04 · Debian 12 / 13**，复制这一条命令运行：

```sh
(wp_tmp=$(mktemp -d) && trap 'rm -rf "$wp_tmp"' EXIT && curl -fsSL --retry 5 --retry-all-errors --retry-max-time 180 --connect-timeout 15 --max-time 60 --proto '=https' --proto-redir '=https' --tlsv1.2 https://github.com/ninex98/webpatch/releases/latest/download/install.sh -o "$wp_tmp/install.sh" && sh "$wp_tmp/install.sh" && /usr/bin/webpatch --version)
```

需要 `curl` 和 root/sudo，无需 Git、虚拟环境或 pip。完整下载后才执行，下载失败就停止。[下载失败、指定版本、卸载 →](docs/installation.md)

<a id="cli-preview"></a>

## CLI 预览

安装成功后，先扫描：

```sh
webpatch scan --lang zh
```

<picture>
  <source media="(max-width: 600px)" srcset="assets/readme/terminal-mobile.svg">
  <img src="assets/readme/terminal.svg" alt="WebPatch 实际输出：检查结果、待核实项和下一步。" width="100%">
</picture>

图为 0.2.0 在 Ubuntu 24.04 / arm64 中的实际英文输出；空清单保持 `UNKNOWN`。[完整采集记录](assets/readme/README.md)。

<a id="commands"></a>

## 常用命令

| 命令 | 效果 |
| :--- | :--- |
| `webpatch scan --lang zh` | 中文显示 PHP 检查结论、证据缺口和下一步 |
| `webpatch scan --details --lang zh` | 展开具体检查和待核实内容 |
| `webpatch plan --lang zh` | 预览候选升级和阻断原因，不安装软件包 |
| `webpatch fix --dry-run --lang zh` | 只检查修复条件，不修改系统 |
| `sudo webpatch fix --lang zh` | 引导审阅和精确确认，可能更新软件包、重启服务 |
| `webpatch scan-node --lang zh` | 检查受支持的 Node.js 运行时，不检查 npm 依赖或修复 Node |
| `webpatch --version` | 查看当前实际调用的版本 |
| `webpatch --help` | 查看命令列表；修复参数用 `webpatch fix --help` |

表中只有经确认的 `fix` 操作会修改服务或软件包，审阅文件与恢复记录由工具管理。修复需要受支持的官方包、认证归档及预部署的验证探针；条件不足就阻断执行。

`UNKNOWN` 表示证据不足，`BLOCKED` 表示当前步骤不能执行，`PARTIAL` 表示可能已发生部分变更。[完整结果解释、退出码与 JSON 导出 →](docs/cli.md#reading-results)

## 支持范围

- **PHP 修复：** Ubuntu 22.04/24.04、Debian 12/13 的官方 amd64 软件包，受支持的 FPM/mod_php 环境；精确确认后进行同分支修复。
- **容器与 Node.js：** 只读清单和容器重建建议；不在容器内原地修复、不自动部署镜像。
- **其他环境：** PPA/Sury/ESM、自编译、不支持的架构及 macOS/Windows 没有认证的修复路径。不提供自动回滚，也不宣称整台服务器安全。

当前 PHP 规则聚焦 PHP2Shell（`CVE-2026-109618` / `CVE-2026-109619`）。内置规则有效至 **2026-10-29 00:00 UTC**，到期后保持 `UNKNOWN`，须经来源审阅后更新。[详细能力与验收记录 →](docs/development-status.md)

## 更多文档

[安装与排错](docs/installation.md) · [CLI 参考](docs/cli.md) · [架构设计](docs/design.md) · [验收证据](evidence/phase-6c-release/README.md)

[参与贡献](CONTRIBUTING.md) · [Apache-2.0 许可证](LICENSE)
