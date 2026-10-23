# 阶段 6C：0.2.0 发布与体验验收 / 0.2.0 release acceptance

**PASS：[v0.2.0](https://github.com/ninex98/webpatch/releases/tag/v0.2.0) 已公开发布。** 2026-10-23 (Asia/Shanghai)。发布标签及制品来自 `c48f06fe72bb99f8c4bac7d7745aa7dd5b39818d`；后续提交仅补充发布入口/验收证据，不覆盖已发布包或重写标签。

| 验收项 / Gate | 结果 / Result |
|---|---|
| 完整安全 CI | **17/17 PASS**, [39905440668](https://github.com/ninex98/webpatch/actions/runs/39905440668) |
| Python fixtures | Python 3.10 / 3.12 各 **647 PASS**，零 failures/errors/skips；JUnit/log 保留 |
| 初始分发 | build + 四发行版各 **23 场景 PASS**, [39905440596](https://github.com/ninex98/webpatch/actions/runs/39905440596)；draft 按设计 skipped |
| 草稿发布流程 | **6/6 PASS**, [39909358670](https://github.com/ninex98/webpatch/actions/runs/39909358670) |
| 新终端修复入口 | Ubuntu 22.04/24.04、Debian 12/13 × FPM/Apache **八格已安装 fix --review 成功**；错误 hash、重复计划均拒绝；显式内部健康故障的另八格保持 PARTIAL / changed=true |
| 公开在线安装 | 四发行版 arm64 新容器 **4/4 PASS**：非 root + sudo，初始无 Python，真实 GitHub 下载及依赖安装，中文摘要 UNKNOWN/exit 2 |
| 现有版本升级 | Ubuntu 24.04 非 root，从公开 **0.1.0 → 0.2.0 PASS**，简洁输出、无 `_apt` unsandboxed 提示 |
| 文档与实现对应 | 发布后 README/版本入口更新，runtime/installer/tests/workflows 与发布标签无差异；本地链接、SVG/XML、摘要验证通过 |

发布 deb SHA256：`6cb409a579e05407b296fb6794ae912356cbaaeae0f31aa04d6e08247156b5e6`。`release-assets-validation.json` 核对 draft target、所有附件、原分发测试安装包和 SHA256SUMS 完全一致。`published-release.json` 保留公开状态与时间。

`safety/validation.json` 保留 506 个下载制品文件的摘要及选存映射。`native-guided-results.json` 记录 8 次成功和 8 次故障结果，原始结果哈希及执行入口明确可查。原生成功运行实际已安装 `/usr/bin/webpatch fix --review ... --format json`，由 PTY 输入完整计划摘要；确认视图 `guided-ui-*.txt`、错误确认/重复拒绝、环境、源码 manifest 和 JUnit 保留。大包及重复多 MB 快照不进 Git，原始内容可从 Actions artifacts 获取；保存路径中的 ci-evidence 改为 results，避免被忽略规则遗漏。

## 在线验证与保留失败 / Live verification and retained failures

`online-harness/` 是实际执行的脚本。复用上阶段的干净基础镜像，每次启动新的 `--rm` 容器，未安装 Python/WebPatch。命令为 `docker run --rm -i webpatch-live-release:<label> bash -s < .../verify.sh`；升级验证同理使用 upgrade.sh。无宿主 mounts、privileged 或生产操作。sudo 在容器中仅允许测试用户无密码执行 apt-get，真实提权及依赖解析通过；密码输入本身未自动化。

Ubuntu 22.04 初次下载和升级测试初次下载分别遇到 GitHub TLS EOF / SSL_ERROR_SYSCALL（curl 35），保留在 jammy-online-install.log 与 noble-upgrade.log；未跳过证书验证，随后在新容器以同一公开命令重试通过。成功路径和镜像/日志摘要在 online-validation.json。新安装器默认不刷 APT 输出，失败完整回显；`--verbose` 可展开。

## 能力边界 / Boundaries

日常流程为 scan → fix 引导审阅，不要求用户手工生成 JSON。UNKNOWN、空清单、未认证归档/来源、缺少探针和不支持环境仍阻断。服务准备与软件包变更分别要求完整 hash，取消不是回滚，恢复文件自动保留。

原生八格验证的是已安装引导入口对既有受控 review 的确认/执行；默认无参数向导的准备协调、取消和文件管理有注入测试，底层 preparation API 有既有原生认证，但完整默认探针部署流程 **NOT_RUN / 不支持自动部署**。不会创建 Web 页面或猜测路由；探针和认证包归档仍需事先具备。

修复仍限官方 amd64、受支持分支 FPM/mod_php。新界面不扩张修复范围、不把包版本判断当成运行安全、不更新规则期限；规则仍在 2026-10-29 00:00 UTC 到期。历史 0.1.0 tag 的观察漂移失败在 6B 留存，未放宽产品门禁。开发宿主 PHP/APT/服务未修改。
