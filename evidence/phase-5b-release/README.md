# 阶段 5B：v0.1.0 发布与在线验收 / Release and live installation acceptance

**PASS — v0.1.0 已公开发布，一键安装在线可用。** 日期：2026-10-23 (Asia/Shanghai)。[Release](https://github.com/ninex98/webpatch/releases/tag/v0.1.0) 与 Git 标签均指向 `fe5b63b2faab53dff73c762181eaa191e8254dcd`。后续 README/证据提交仅更新发布入口和记录，不重建或覆盖已发布制品，也不把旧 CI 冒充为新功能验证。

## 范围与验收 / Scope and acceptance

在用户授权后推送 5A 提交，要求该精确源码的完整 safety CI、四格 distribution 测试和受控 Release 草稿流程通过；核对 tag/源码/制品摘要再公开发布；在没有 Python 的新 disposable 容器以普通用户执行真实公开安装命令。最后将中英文 README 默认入口从源码开发安装切换到一键安装。

| Gate | Actual result / evidence |
|---|---|
| 精确源码 safety CI | **17/17 PASS**, [39893453801](https://github.com/ninex98/webpatch/actions/runs/39893453801); `safety-run.json`, `safety/` |
| Python fixtures | **617/617 PASS** on Python 3.10 and 3.12, no failures/errors/skips; 两份 JUnit/log 保留 |
| 初始 distribution CI | **build + 4 install jobs PASS**, draft 按设计 SKIPPED；[39893453827](https://github.com/ninex98/webpatch/actions/runs/39893453827), `distribution/` |
| 手动 Release 草稿流程 | **6/6 PASS**, [39894909468](https://github.com/ninex98/webpatch/actions/runs/39894909468); `draft-workflow-run.json`, `draft-matrix/` |
| 发布身份与制品核对 | **PASS**, `release-asset-validation.json`, `draft-release.json`, `published-release.json`; draft target、最终 tag 与受测 SHA 一致 |
| Ubuntu 22.04 / 24.04、Debian 12 / 13 真实公开安装 | **4/4 PASS**, local arm64 disposable containers; `*-online-install.log`, `online-validation.json` |
| 后续公开文档、链接和版本徽章 | **PASS**, `documentation-validation.json`; 未修改 src/tests/scripts/workflows/installer |

发布 `.deb` SHA256：`e203caefd110255c3e0483a12bc5b0c1d008fc3e2633b616cf016b6c7f9f06a9`。与 5A 的本地包、push distribution 包、手动 draft distribution 包及实际 Release 附件完全一致。本地 arm64 与 hosted amd64 四种发行版各已验证 21 场景，未用不同二进制替代发布制品。

## 真实在线测试 / Live public tests

`online-harness/` 保存实际 Dockerfile 与验证脚本，镜像和日志摘要在 `online-validation.json`。测试从四个官方基础镜像建立普通用户；镜像构建仅安装 curl、CA 证书和 sudo，断言 `/usr/bin/python3` 不存在。sudoers 仅在 disposable 容器允许测试用户对 apt-get 免密码提权；未传入任何 GitHub token 或宿主凭据。

容器随后运行与 README 完全相同的公开 `curl .../releases/latest/download/install.sh | sh` 命令：真实访问 GitHub、验证版本包/摘要，经 sudo 使用 APT 从发行版源安装 Python 和 WebPatch。安装后验证 `webpatch --version` 为 0.1.0、help 可运行，以及非 root `scan` 的空清单保持 UNKNOWN / safe=false / exit 2；扫描前后 dpkg status 摘要相同。

构建：`docker build --build-arg BASE=<official-base> -t webpatch-live-release:<label> ci-evidence/live-installer`。运行：`docker run --rm webpatch-live-release:<label>`。测试需要外网；没有 privileged、宿主目录/proc/socket 挂载。为测试真实 sudo 使用普通容器默认权限，未设置会禁止提权的 no-new-privileges。

## 证据边界 / Boundaries

- `safety/validation.json` 记录完整 482 个下载制品文件的 SHA256，保存选定 JUnit、日志、环境、manifest、结果与失败路径审计；大型重复快照/包留在忽略的 `ci-evidence/` 和原 Actions artifacts，不加入 Git。
- `manifest.json` 记录发布源码、后续文档、制品及本阶段证据摘要。测试/源码均明确对应 fe5b63b，文档提交不改变该事实。5A 中的早期 502 和过严容器 capability 失败仍保留，不重写历史结果。
- 真实在线测试覆盖 arm64 四格，hosted amd64 四格使用真实 APT/dpkg 与离线 GitHub 传输夹具；不声称已测试任意架构/发行版。密码交互本身未自动化；免密码 sudo 的实际提权已测试。
- 扫描/修复支持范围保持原有边界。当前受控修复仅限官方 amd64 profiles；安装成功不表示系统安全。内置规则仍于 **2026-10-29 00:00 UTC** 到期。
- GitHub HTTPS + SHA256 校验不是独立发布者签名。公共签名 APT 仓库、macOS/Windows 安装与主机 PHP/APT/服务修改均未执行。
