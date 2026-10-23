# Linux 安装与发布 / Linux installation and releases

**当前状态（2026-10-23）：[v0.2.0 已公开发布](https://github.com/ninex98/webpatch/releases/tag/v0.2.0)。** / v0.2.0 is published. The commands below download the versioned GitHub Release package.

## 用户安装 / Install

安装器默认只显示进度和结果；需要完整 APT 输出时，在脚本后加 `--verbose`。安装失败会自动显示完整错误。

支持 Ubuntu 22.04/24.04 和 Debian 12/13。需要现有 `curl`、CA 根证书、APT/dpkg、网络访问 GitHub，以及 root 或 sudo 安装权限。无需 Git、venv、pip。Python 3.10+ 是 `.deb` 的系统依赖，由 APT 解析；不自行编译或覆盖系统 Python。系统源及索引必须可用，安装器不自动刷新索引或增加源。

Paste the following block to install or upgrade. It retries failed script downloads, executes only after a complete successful download, and prints the installed version:

```sh
(
  set -eu
  webpatch_tmp=$(mktemp -d)
  trap 'rm -rf "$webpatch_tmp"' EXIT
  curl -fsSL --retry 5 --retry-all-errors --retry-max-time 180 \
    --connect-timeout 15 --max-time 60 \
    --proto '=https' --proto-redir '=https' --tlsv1.2 \
    https://github.com/ninex98/webpatch/releases/latest/download/install.sh \
    -o "$webpatch_tmp/install.sh"
  sh "$webpatch_tmp/install.sh"
  /usr/bin/webpatch --version
)
```

临时文件会自动清理，无需手动管理。上面的重试只覆盖入口脚本的下载；已发布的 0.2.0 安装器后续下载也可能因网络中断失败。需要固定版本时，将 URL 中的 `latest/download` 改为 `download/v0.2.0`，并将执行行改为 `sh "$webpatch_tmp/install.sh" --version 0.2.0`。只有安装成功并确认 `webpatch --version` 为 0.2.0 或更新版本后，才使用 `--lang zh` / `fix`。

如需先审阅脚本，可自行下载后阅读再执行；快速安装段落在下载成功后会立即运行脚本。

安装脚本先识别系统，解析具体版本，再下载 `.deb` 和 `SHA256SUMS`，验证摘要及包名/版本/架构，最后仅对 APT 调用使用 sudo。安装过程中不运行 scan/apply、PHP 命令或服务操作。APT 会安装 WebPatch 及所需依赖；如果 APT 失败，应查看其错误，不把失败当成功。校验和与包都来自 GitHub HTTPS，防止损坏和版本混用，但不是独立发布者签名。

The installer installs the CLI at `/usr/bin/webpatch`. Scan exit codes `1` (potentially affected) and `2` (unknown/incomplete) are expected assessment outcomes, not installation failures. An empty inventory stays UNKNOWN. Installation does not establish runtime safety.

<a id="download-troubleshooting"></a>

## 下载失败或参数不识别 / Download and version troubleshooting

`curl: (56) ... unexpected eof while reading` 表示接收网络数据时连接异常结束。`(35)` 是 TLS 连接阶段错误。仅凭这些日志不能判断是 GitHub/CDN、网络路由、代理还是本机链路中断；旧版本曾成功下载也不保证新的一次连接成功。[curl 官方错误说明](https://curl.se/libcurl/c/libcurl-errors.html)

原来的 `curl ... | sh` 没有等待下载完成，且普通 shell 默认只以管道最后一个命令判断状态。下载失败后另起一行执行 `webpatch scan --lang zh`，可能仍在调用旧版。新指令使用私有临时文件、`set -e` 和 [curl 重试选项](https://curl.se/docs/manpage.html#--retry-all-errors)，避免执行下载失败的脚本；它不会关闭证书校验，也不能修复持续不可达的网络。

先确认当前命令来自哪里：

```sh
webpatch --version
command -v webpatch
type -a webpatch
/usr/bin/webpatch --version
```

若普通 `webpatch` 与 `/usr/bin/webpatch` 版本不同，检查 PATH、别名或旧虚拟环境。若版本仍是 0.1.0，`--lang` 不识别是预期结果，说明当前调用的程序尚未更新。

### 直接安装已校验的 0.2.0 包 / Checked package fallback

如果入口脚本的下载仍中断，可使用下面这段固定版本命令。它只下载一个官方 Release 包，强制 IPv4/HTTP 1.1 作为另一条连接尝试，重试失败下载，核对公开 SHA256 后才调用 APT。不能据此认定原错误一定由 IPv6 或 HTTP/2 引起；仅有 IPv6 的环境应移除 `-4`。

```sh
(
  set -eu
  webpatch_tmp=$(mktemp -d)
  trap 'rm -rf "$webpatch_tmp"' EXIT
  curl -4 --http1.1 -fsSL --retry 5 --retry-all-errors --retry-max-time 180 \
    --connect-timeout 15 --max-time 60 \
    --proto '=https' --proto-redir '=https' --tlsv1.2 \
    https://github.com/ninex98/webpatch/releases/download/v0.2.0/webpatch_0.2.0_all.deb \
    -o "$webpatch_tmp/webpatch_0.2.0_all.deb"
  printf '%s  %s\n' \
    '6cb409a579e05407b296fb6794ae912356cbaaeae0f31aa04d6e08247156b5e6' \
    "$webpatch_tmp/webpatch_0.2.0_all.deb" | sha256sum -c -
  chmod 0711 "$webpatch_tmp"
  chmod 0644 "$webpatch_tmp/webpatch_0.2.0_all.deb"
  if [ "$(id -u)" -eq 0 ]; then
    apt-get install -y --no-install-recommends --no-remove "$webpatch_tmp/webpatch_0.2.0_all.deb"
  else
    sudo apt-get install -y --no-install-recommends --no-remove "$webpatch_tmp/webpatch_0.2.0_all.deb"
  fi
  /usr/bin/webpatch --version
)
```

确认显示 `0.2.0` 后，运行 `webpatch scan --lang zh`。扫描退出码 1/2 是检查结论，不是升级失败。

上述 SHA256 对应 [v0.2.0 的官方安装包](https://github.com/ninex98/webpatch/releases/download/v0.2.0/webpatch_0.2.0_all.deb) 与 [SHA256SUMS](https://github.com/ninex98/webpatch/releases/download/v0.2.0/SHA256SUMS)。如果服务器始终无法连接 GitHub，可在能访问 GitHub 的电脑下载这两个文件，传到服务器，先执行 `sha256sum -c SHA256SUMS --ignore-missing`，确认包校验成功，再使用 `sudo apt-get install ./webpatch_0.2.0_all.deb`。校验列表来源仍是 GitHub HTTPS，不是独立发布者签名。

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
