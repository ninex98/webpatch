# Linux 安装与发布 / Linux installation and releases

**当前状态（2026-10-23）：[v0.1.0 已公开发布](https://github.com/ninex98/webpatch/releases/tag/v0.1.0)。** / v0.1.0 is published. The commands below download the versioned GitHub Release package.

## 用户安装 / Install

安装器默认只显示进度和结果；需要完整 APT 输出时，在脚本后加 `--verbose`。安装失败会自动显示完整错误。

支持 Ubuntu 22.04/24.04 和 Debian 12/13。需要现有 `curl`、CA 根证书、APT/dpkg、网络访问 GitHub，以及 root 或 sudo 安装权限。无需 Git、venv、pip。Python 3.10+ 是 `.deb` 的系统依赖，由 APT 解析；不自行编译或覆盖系统 Python。系统源及索引必须可用，安装器不自动刷新索引或增加源。

Install the latest release with one command:

```sh
curl -fsSL --proto '=https' --tlsv1.2 https://github.com/ninex98/webpatch/releases/latest/download/install.sh | sh
```

To inspect the script first, download it to a private directory, read it, then run it. To pin a release:

```sh
curl -fsSL --proto '=https' --tlsv1.2 https://github.com/ninex98/webpatch/releases/download/v0.1.0/install.sh | sh -s -- --version 0.1.0
webpatch --version
webpatch scan
```

安装脚本先识别系统，解析具体版本，再下载 `.deb` 和 `SHA256SUMS`，验证摘要及包名/版本/架构，最后仅对 APT 调用使用 sudo。安装过程中不运行 scan/apply、PHP 命令或服务操作。APT 会安装 WebPatch 及所需依赖；如果 APT 失败，应查看其错误，不把失败当成功。校验和与包都来自 GitHub HTTPS，防止损坏和版本混用，但不是独立发布者签名。

The installer installs the CLI at `/usr/bin/webpatch`. Scan exit codes `1` (potentially affected) and `2` (unknown/incomplete) are expected assessment outcomes, not installation failures. An empty inventory stays UNKNOWN. Installation does not establish runtime safety.

## 升级、卸载与边界 / Upgrade, uninstall and boundaries

再次运行安装命令即可升级到最新 Release；同版本可以重复运行，指定更旧版本会被拒绝。不会后台自动更新程序或规则。升级后，旧准备收据/修复计划可能因实现摘要不同而失效，须重新审阅生成。程序版本和规则有效期独立；当前规则到期日为 2026-10-29 00:00 UTC，不能只改日期续期。

```sh
sudo apt-get remove webpatch
```

卸载仅移除工具包。已有 `/var/lib/webpatch` 审计/状态、导出的报告及显式准备操作产生的服务状态需要按维护文档处理；卸载不恢复 PHP、不回滚事务、不撤销服务准备。先按 [CLI](cli.md) 检查并处理仍有效的准备收据。

| 系统 | 安装入口 | 能力边界 |
|---|---|---|
| Ubuntu 22.04 / 24.04、Debian 12 / 13 | 本安装器 + architecture-independent `.deb` | 运行时 Python ≥3.10；修复仍仅认证的官方 amd64 FPM/mod_php profiles |
| 其他 Linux 发行版 / 衍生系统 | 安装器明确拒绝 | 源码试用不代表支持完整扫描/修复 |
| macOS / Windows | 安装器明确拒绝 | 未提供经验证的本地扫描/修复支持 |

没有公共 APT 仓库，因此 `apt install webpatch` 不能代替此下载入口。`.deb` 中没有 maintainer scripts 或后台服务。工具安装与 PHP 受控修复是两个独立动作。

## 维护者发布 / Maintainer release process

1. 唯一程序版本来源是 `src/webpatch/__init__.py` 的 `__version__`，格式 `MAJOR.MINOR.PATCH`。Python 元数据、CLI、`.deb` 构建及测试读取同一来源。版本标签为 `vMAJOR.MINOR.PATCH`。更新版本时同步发布说明和面向用户的版本展示。
2. 在项目虚拟环境执行 fixtures，在 disposable 容器构建/安装包；保存源码、安装包摘要、日志和环境。`WebPatch distribution` 在 push/PR 构建一次发布包，再将同一制品送入四格 Ubuntu/Debian 安装测试。Linux 安装测试的 GitHub 下载传输由离线夹具替代；真实在线链路需发布后单独验证。
3. 发布的同一 main commit 必须通过 `WebPatch safety checks`。手动运行 `WebPatch distribution`，选择 `create_draft=true`，四格安装及精确 SHA 安全 CI 门禁通过后仅创建草稿 Release。默认运行只生成 Actions artifacts，不写 Release。
4. 审阅草稿源码、版本、SHA256SUMS、支持边界及规则有效期，再单独公开发布。若规则已过期，先审阅官方来源并产生新版本，或明确保持 UNKNOWN；不能把旧 CI 当成新源码的证明。建议为仓库启用 GitHub immutable releases；当前流程没有自动修改该设置。
5. 公开发布后，在新的 disposable 容器/hosted VM 验证真实 GitHub 安装入口。校验通过才宣布在线一键安装可用。后续修正用新版本，不覆盖已发布包或重写标签。

Release artifacts: `webpatch_<version>_all.deb`, `install.sh`, `LICENSE`, `SHA256SUMS`. Python wheel/sdist can still be built for developers; PyPI publication and signed APT repository hosting are outside this stage.
