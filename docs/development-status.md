# 开发状态 / Development status

核对日期：2026-10-23（Asia/Shanghai）。**原设计四阶段已按声明的有限范围完成并分别验收。** 原四阶段最终受测功能/测试/CI 源码 `941040c06cb29fc73cf64dcf81a78867d033f3e8`，Actions [39888070774](https://github.com/ninex98/webpatch/actions/runs/39888070774) **17/17 PASS**。最终文档/证据提交晚于受测源码；源码一致性、制品摘要、日志/JUnit 和各项结果见 [最终验收](../evidence/final-acceptance/README.md)。

## 阶段 6：终端体验与引导修复 / Readable terminal and guided repair

**[v0.2.0 已发布](https://github.com/ninex98/webpatch/releases/tag/v0.2.0)**，受测源码 `c48f06fe72bb99f8c4bac7d7745aa7dd5b39818d`。[Safety CI 39905440668](https://github.com/ninex98/webpatch/actions/runs/39905440668) **17/17 PASS**，Python 3.10/3.12 各 647 tests；[分发 39905440596](https://github.com/ninex98/webpatch/actions/runs/39905440596) 构建和四种发行版各 23 场景通过；[草稿流程 39909358670](https://github.com/ninex98/webpatch/actions/runs/39909358670) **6/6 PASS**。

默认 scan/plan 输出为人类可读摘要；支持中英文、自动颜色/NO_COLOR、窄终端和 --details，JSON/退出码保持。安装器默认显示进度与结果，失败显示完整 APT 日志。`webpatch fix` 自动管理审阅和恢复记录，服务准备和包修复仍分别确认精确 hash；预部署探针、认证归档、严格门禁和持锁复核仍必需。

八格原生成功路径使用已安装 `fix --review` 的真实 terminal 输入精确摘要并完成升级/验证；错误确认与重放均拒绝。完整默认向导自动部署探针不在支持范围；默认向导的准备协调/取消路径以注入测试验证，原生准备 API 沿用既有认证。历史 v0.1.0 tag 的一次观察漂移失败保留，不放宽准入。阶段记录见 [6A](../evidence/phase-6a-terminal/README.md)、[6B](../evidence/phase-6b-guided/README.md) 与 [6C 发布验收](../evidence/phase-6c-release/README.md)。

## 阶段 5A / 5B：Linux 分发与发布 / Linux distribution and publication

**[v0.1.0 已公开发布](https://github.com/ninex98/webpatch/releases/tag/v0.1.0)**，源码 `fe5b63b2faab53dff73c762181eaa191e8254dcd`。同一源码的 [safety CI 39893453801](https://github.com/ninex98/webpatch/actions/runs/39893453801) **17/17 PASS**；[distribution 39893453827](https://github.com/ninex98/webpatch/actions/runs/39893453827) 构建及四格安装通过；[Release 草稿流程 39894909468](https://github.com/ninex98/webpatch/actions/runs/39894909468) **6/6 PASS**，随后公开发布。

Ubuntu 22.04/24.04、Debian 12/13 可使用一键安装脚本；无需 Git、venv、pip。程序、Python 元数据、Debian 包和测试读取单一版本来源。安装器校验固定版本的 SHA256 及包身份后使用 APT 安装工具/必要依赖，拒绝不支持的系统及降级请求。

617 fixtures 在 Python 3.10/3.12 均通过。发布包 SHA256 `e203caefd110255c3e0483a12bc5b0c1d008fc3e2633b616cf016b6c7f9f06a9` 与本地包完全一致；四种发行版的本地 arm64 及 hosted amd64 分别通过每格 21 场景。最初 CI-pending 状态见 [5A 历史记录](../evidence/phase-5a-installation/README.md)，最终发布/在线验证见 [5B 证据](../evidence/phase-5b-release/README.md)。安装方式见 [安装说明](installation.md)。

发布后的文档/证据提交不改变标签或已发布包。安装支持不扩张修复 profile；程序版本不自动延长规则有效期。

## 原设计四阶段

| 阶段 | 交付及验收 |
|---|---|
| 1 只读基础 | 注入 I/O、发现/规则/模型、CLI、可构建 .deb、只读反例；在后续矩阵持续验证 |
| 2 可信发现与 dry-run | 实例/文件/来源/路由证据、结构化覆盖、APT 模拟、不可变诊断计划和漂移检查；2D 独立历史证据在 [phase-2d4](../evidence/phase-2d4/README.md) |
| 3 有限 Ubuntu 修复 | 内核请求绑定、受控只读配置视图、全 task FD census、精确维护合同、具体 hash 确认、持锁事务及修复后验证/审计；22.04/24.04 × FPM/mod_php 四格已安装公开 CLI 实际升级通过，显式健康故障为 PARTIAL |
| 4A 容器建议 | Ubuntu 22.04/24.04、Debian 12 三格只读/禁网容器验证逐 CVE 建议和 image digest 声明；build/push/rollout NOT_RUN |
| 4B Node.js | 独立 adapter/rules，Debian 12/13 两项运行时 CVE；两格原生容器验证包/改名进程及只读状态；无 npm 审计或 Node 修复 |
| 4C Debian PHP | 独立签名根和归档双格、精确 profile、准备/事务；12/13 × FPM/mod_php 四格独立 QEMU 客体完成已安装 CLI 升级及显式健康故障 |

17 项包括 Python 3.10/3.12（各 617 tests，0 failed/errors/skipped）、三格包安装/只读/重建建议容器、两格 Node、两格 Debian 归档、四格 Ubuntu VM 和四格独立 Debian VM。八格成功路径调用已安装 `/usr/bin/webpatch apply`，工作目录 `/`；错误 hash、同计划重复调用均拒绝。八格故障路径通过明确测试能力，在实际升级和重启后请求不可用 loopback 端口，保留 changed=true 的 PARTIAL；生产 CLI 没有故障开关。

## 增量交付与失败留存

| 提交 | 实际结果与证据 |
|---|---|
| `829df71` | 11/11 的受控准备/收据、包能力与扩展基线；[记录](../evidence/accepted-829df71/README.md)，仅适用于当时源码 |
| `2d8132c` | 605 本地 PASS；39883475413 为 17/17，内部升级/故障基线；前次失败在 [phase-3g4](../evidence/phase-3g4/README.md) |
| `98a3071` / `c841096` | 分别留存 [Debian 独立验收](../evidence/phase-4c-accepted/README.md) 与 [Ubuntu 内部矩阵](../evidence/phase-3g-accepted/README.md) |
| `d314ead` | 双语操作说明及包内文档；同轮两格 Apache 的故障场景因安装前观察竞争被正确阻断，失败记录在 [phase-3h-public](../evidence/phase-3h-public/README.md) |
| `ba5d9f6` / `da666b1` | 开启精确确认入口并留存 [八格已安装 CLI 验收](../evidence/phase-3h-accepted/README.md)；617 本地 PASS。整轮 15/17，Ubuntu 最小镜像过滤文档导致两格容器失败 |
| `941040c` | 隔离容器测试安装显式包含 WebPatch 文档；完整 17/17 PASS。此前原日志和本地测试在 [phase-packaging-docs](../evidence/phase-packaging-docs/README.md) |

观察竞争始终阻断产品。CI 仅在 changed=false 且明确为短命进程/输入稳定性竞争时，最多生成三份新计划，并保存每份审阅和结果；不重试同一计划，不重试已变更/健康/来源/过期失败。最终证据中的 all-attempts.json 包含这些尝试，不能只取最后一次成功隐藏失败。

## 当前接口与边界

报告 schema 2、诊断计划 schema 4；`repair-plan` 的 wrapper schema 1 内含 schema 5 Plan。诊断 READY_FOR_REVIEW 不授权执行；受控 READY_FOR_CONFIRMATION 仍须具体 hash 确认及持锁重新验证。全部结果 safe=false，成功仅为 VERIFIED_WITHIN_DECLARED_SCOPE。操作流程见 [CLI](cli.md)，合同见 [阶段三](phase-3.md) 和 [扩展](phase-4.md)。

有限修复 profile：Ubuntu 22.04/php8.1、24.04/php8.3、Debian 12/php8.2、13/php8.4，官方同分支 amd64、标准 FPM/mod_php、完整已安装 PHP source cohort。未知消费者/实例、特殊 APT/dpkg 配置、依赖变更、复杂预依赖、其他架构/源/分支继续阻断。不支持 PPA/Sury/ESM、自编译、CGI/FrankenPHP/LiteSpeed、容器原地修复或任意生产站点认证。没有自动回滚或无人确认执行。

collector 协议 3，只接受两项已审阅默认 INI 指令的新增，既有设置变化继续阻断。PHP/Node 规则至 **2026-10-29 00:00 UTC** 到期；之后必须重新审阅官方来源，不能只改日期。Debian 客体镜像以官方 HTTPS/SHA512 验证传输/内容，镜像签名 NOT_AVAILABLE；产品 APT 签名链独立验证。

开发宿主 PHP/APT/系统包/服务未修改；实际安装/服务测试仅在 disposable 容器、GitHub hosted Ubuntu VM 与独立 Debian 客体发生，没有漏洞利用或生产修复。原 README/SVG 工作由 `13c6c9c` 保存，视觉资源保持。自动镜像构建/发布、npm 修复、公开签名 APT 仓库不在原设计四阶段范围内，也未执行；版本化 Release 由上述独立 5A/5B 阶段交付。

## Docker discovery (0.3.0 release candidate)

`scan` now has a separate read-only local Docker adapter and per-container output. It reads bounded metadata without installing WebPatch or executing commands inside containers, reuses the existing Ubuntu/Debian rules, and keeps custom PHP/Alpine evidence UNKNOWN. Host repair admission is unchanged. See [CLI usage](cli.md#local-docker-discovery-030) and the new stage evidence in [phase-9-docker](../evidence/phase-9-docker/README.md). The 0.3.0 release candidate is awaiting its exact-source safety/distribution CI; it is not in 0.2.0.
