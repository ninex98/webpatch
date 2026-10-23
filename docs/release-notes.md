# WebPatch 0.1.0 — Linux preview / Linux 预览版

首次版本化 Linux 分发：Ubuntu 22.04/24.04、Debian 12/13 可使用一条命令下载安装 WebPatch，无需 Git、venv 或 pip。安装器解析具体 Release、验证 SHA256 和包元数据，通过 APT 安装工具及必要依赖，拒绝降级。不执行 PHP 修复或扫描。

First versioned Linux distribution: one-command installation on Ubuntu 22.04/24.04 and Debian 12/13 without Git, venv or pip. The installer resolves a concrete release, checks SHA256 and package metadata, installs the tool and required dependencies through APT, and rejects downgrades. It does not scan or repair PHP.

The package is architecture-independent Python and requires Python 3.10+ (resolved through APT). Installation portability does not extend the certified repair profiles: official amd64 PHP packages, supported FPM/mod_php, complete evidence and exact plan-hash confirmation remain required. macOS, Windows and other Linux distributions are not supported by this installer. There is no public APT repository.

Bundled PHP/Node rules expire at **2026-10-29 00:00 UTC**. After expiry assessments remain UNKNOWN until a source-reviewed rules release; updating the program never silently extends rule validity. Installation and package-version matches do not establish runtime safety.

Checksums detect corrupted or mismatched assets obtained through GitHub HTTPS; they are not an independent publisher signature. This release has no separate package signing key. For installation, upgrade and uninstall instructions see [the installation guide](https://github.com/ninex98/webpatch/blob/main/docs/installation.md).
