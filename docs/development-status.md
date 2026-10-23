# 开发状态 / Development status

核对日期：2026-10-23（Asia/Shanghai）。**原设计四阶段已按声明的有限范围完成并分别验收。** 最新受测功能/测试/CI 源码 `941040c06cb29fc73cf64dcf81a78867d033f3e8`，Actions [39888070774](https://github.com/ninex98/webpatch/actions/runs/39888070774) **17/17 PASS**。最终文档/证据提交晚于受测源码；源码一致性、制品摘要、日志/JUnit 和各项结果见 [最终验收](../evidence/final-acceptance/README.md)。

## 阶段 5A：Linux 分发准备 / Linux distribution preparation

新增独立的版本化分发阶段：Ubuntu 22.04/24.04、Debian 12/13 一键安装脚本、单一版本来源、Release assets/SHA256SUMS 及四格分发 CI。**本地验证 PASS；远端 CI_PENDING，首个 Release 尚未发布，在线安装 NOT_RUN。** 617 fixtures 通过；同一个 `.deb` 在四个 arm64 disposable 容器完成安装、重装、升级、拒绝降级、错误包阻断和只读 UNKNOWN 验证。完整日志、失败留存和摘要见 [阶段 5A 证据](../evidence/phase-5a-installation/README.md)，用户入口见 [安装说明](installation.md)。

旧的 17/17 仅证明原记录的源码，不能作为本阶段 CI 通过的证据。新增 workflow 默认只构建和测试，显式手动操作才生成 Release 草稿，并要求同一 main SHA 的安全 CI 通过；公开发布和发布后的真实 GitHub 下载链路须单独验收。安装覆盖不扩张任何修复 profile。

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

开发宿主 PHP/APT/系统包/服务未修改；实际安装/服务测试仅在 disposable 容器、GitHub hosted Ubuntu VM 与独立 Debian 客体发生，没有漏洞利用或生产修复。原 README/SVG 工作由 `13c6c9c` 保存，视觉资源保持。自动镜像构建/发布、npm 修复、公开签名 APT 仓库和正式 Release 均不在本次原设计四阶段范围内，也未执行。
