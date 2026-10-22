# 开发进度与下一阶段 / Development status and next stage

核对日期：2026-10-22（Asia/Shanghai）。最新验收功能/测试/CI 源码为 `efb122d9415ad2819c02fb958209b0e771d4715b`；Actions [39763873264](https://github.com/ninex98/webpatch/actions/runs/39763873264) 全部 9 项 PASS。对应源码/制品哈希、JUnit、平台与 VM 结果见 [2D.4 当前源码核对](../evidence/phase-2d4/current-source-validation.json)。文档/证据提交可以晚于该源码；后续开发仍须重新检查 Git、CI 和源码摘要。

## 对应原始计划的位置

原始四阶段计划见 [design.md](design.md) 第 5 节，初始版本为 `75e3870`。“2D”是原阶段二剩余门禁的拆分，不能解释为原计划阶段三已完成。

| 原计划 | 当前状态 | 证据与边界 |
|---|---|---|
| 阶段 1：只读基础 | 已完成 | 阶段一与云端基线证据保留 |
| 阶段 2：可信发现与真实 dry-run | 2A/2B/2C 及本轮 2D 各自限定的只读范围已验收；完整执行准入尚未闭合 | [2C](../evidence/phase-2c/README.md)、[2D.4](../evidence/phase-2d4/README.md)；完整消费者、加载配置和请求归属等仍 UNKNOWN |
| 阶段 3：有限修复 | 未实现 | 没有 executor，apply 始终拒绝；计划确认、受控执行、修复后健康验证和失败审计待开发 |
| 阶段 4：扩展 | 未实现核心扩展 | Debian 修复、Node.js、自动镜像重建和公开签名仓库仍需独立开发/认证 |

准确位置仍是**原阶段二末尾、阶段三前置证据接口之前**。当前可以审阅有明确范围和证据的诊断计划，不能自动修复生产系统。

## 本轮分阶段交付

| 小阶段 | 提交 | 实际验收 |
|---|---|---|
| 2D.1 结构化覆盖与作用域 | `4a632e0` | 303 本地 tests PASS；[39759702439](https://github.com/ninex98/webpatch/actions/runs/39759702439) 9/9 PASS |
| 2D.2 运行映像、模块与静态路由证据 | `0833be6`（CI 待验收检查点） | 322 本地 tests PASS；首轮四格 VM 在读取保存计划时 FAIL，完整保留；修正后由后续两轮四格 VM 验收 |
| 2D.3 统一门禁与时效 | `d5447b3` | 336 本地 tests PASS；[39763556960](https://github.com/ninex98/webpatch/actions/runs/39763556960) 9/9 PASS |
| 2D.4 真实环境与反例 | `efb122d` | 336 本地 tests PASS；[39763873264](https://github.com/ninex98/webpatch/actions/runs/39763873264) 9/9 PASS |

最终 Python 3.10/3.12 各 336 tests；Docker Ubuntu 22.04、24.04、Debian 12 三格 PASS；Ubuntu 22.04/php8.1、24.04/php8.3 × FPM/mod_php 四格 VM PASS。新验收包括多个 FPM pool/socket、标准 PHP 映射的文件身份、门禁引用、真实无害映射删除/替换、配置变化反例，以及扫描/模拟前后相关 PHP/Apache PID/starttime、配置/APT/dpkg 状态不变。

首次 2D.2 失败原因是 FPM 约 1.45 MiB、Apache 约 3.82 MiB 的保存计划超过通用 1 MiB 文本限制。修正为独立 16 MiB 计划读取接口，配置/procfs 限制保持；未降低签名、哈希或门禁要求。失败日志/制品在 [first-ci](../evidence/phase-2d2/first-ci/)，后续成功记录独立保留。测试没有漏洞利用、旧漏洞二进制安装或 WebPatch 实际修复。

## 当前接口与尚缺准入

报告 schema 2、计划 schema 4；旧 schema 2/3 计划须重新扫描。实体覆盖包含 VERIFIED、OBSERVED、UNKNOWN、UNSUPPORTED、NOT_CHECKED，均带明确主体、证据、原因和下一步。选择包不会缩小扫描范围或隐藏同包消费者。精确的文件认证、进程本地关联、监听 socket、静态配置、实际加载状态和请求归属相互独立。

READY_FOR_REVIEW 仅表示诊断输入可审阅；所有计划仍 `admission_status=BLOCKED`、`executable=false`。规则与索引时效、配置/映像/namespace/新实例、目标/依赖和门禁语义漂移会拒绝保存计划；不把安装成功、版本达标、缓存包一致或无变更模拟当运行时安全。

阶段三仍须依次闭合：

1. 经审阅的完整消费者清单和明确目标作用域，覆盖隐藏/空闲实例、自定义安装与共享包影响。
2. 显式且可信的加载配置/请求归属证据接口，绑定 scope/boot/PID/starttime/映像/模块/配置/时效；默认扫描仍不执行配置、不发 HTTP、不部署页面。
3. 全部获批依赖变化、候选维护脚本/triggers/conffile 策略、真实安装与隔离模拟的差异审阅，以及所有受影响服务的停机预算和人工恢复方案。
4. 具体 plan hash 的显式确认、持锁事务及执行前复核、修复后运行时/路由/健康验证和 FAILED/PARTIAL 等失败审计；不承诺 APT 自动回滚。

只读证据未证明的关系继续阻断；TCP listener、自定义模块/原生依赖的穷举、外部 namespace、第三方/PPA/Sury/ESM、Debian 修复均未因此获得执行支持。有限 VM 测试站点不是任意生产环境保证。规则有效期仍为 2026-10-29 00:00 UTC，本轮未更改或延长。

## 后续交接与工作区

下一轮入口见 [next-conversation-prompt.md](next-conversation-prompt.md)，接口/迁移见 [phase-2d.md](phase-2d.md) 和 [CLI 使用说明](cli.md)。遵循 AGENTS.md：小阶段先定验收，保存当前源码证据后立即双语提交；云端检查点明确 CI pending，失败后续修正，不强推。

开工时 README、双语文档和视觉资源的未提交工作已由独立提交 `13c6c9c` 保存，本轮功能提交没有覆盖这些内容。开发宿主 PHP、APT、系统包和服务未被修改；安装、服务准备和故障注入仅发生在隔离 CI 环境。

## 2026-10-23 活动开发：按原设计四阶段继续

用户已明确授权按原设计四阶段继续，Debian、Node.js 与容器重建扩展分别验收；先闭合有限 Ubuntu PHP 修复。2D 的历史验收不变。当前新增：3A.1 `a0d63da`（354 tests，CI 39767703025 9/9 PASS）；3A.2 `b52b011` 首轮 8/9，既有 helper 寿命问题由 `cc84680` 修正（该独立重跑一格取消，不计通过）；3B `f909217`（395 tests，39776918742 9/9 PASS，包含修正后的真实探针）；3C `5b22ed3`（415 tests，39791877691 9/9 PASS）；3D.1 `66d2e26`（427 tests，39794945409 9/9 PASS）。

新增归档封存检查点在暂存源码隔离目录验证 434 tests，证据见 evidence/phase-3d-archive，Linux 全矩阵待重验。3D.2 受控服务准备/只读配置快照仍在开发，尚未验收。3C 仅是注入后端事务状态机，不能宣称真实修复已完成；实际安装执行器、完整准入与阶段四仍须继续。接口演进见 docs/phase-3.md。

## 当前增量状态（2026-10-23，继续开发中）

归档封存修正 `6d374f1` 的 Actions 39820064701 已 9/9 PASS。受控启动 `dfcd025` 首轮失败保存在 evidence/phase-3d2/first-ci；`bd39f76` 修正共享 include 和空属性后，systemctl 结构化 EnvironmentFiles 空数组仍省略，由 `dcd3eb2` 增加固定 typed D-Bus 读取。`9c2bbaf` 补齐额外测试 pool 的 socket 访问并保存受限错误码，尚待完整四格重验；单格 Apache 通过不能扩张为全矩阵通过。

执行输入 `509f83c` 遇到 runner 特殊 dpkg hooks 并按要求阻断；`040f213`/`caa9517` 仅在临时 VM 建立记录过的无特殊 hook 测试基线，产品门禁未放宽。包操作能力 `1db0afb` 经 `2ef6b0b` 调整独立 Docker runtime 测试，三格真实合成包升级/trigger/锁/失败路径 PASS，在 9160700 留证时核对 9 个相关源码文件与受测 commit 一致，证据在 evidence/phase-3e2/accepted-native。此结果不等于真实 PHP 修复。

当前收据复核 `816b8bb` 增加签名、代码/规则、scope、实例、只读视图和新请求核对；容器重建建议 `857e346` 本地 500 tests PASS；独立 Node adapter/rules `8fccbc8` 本地 519 tests PASS。4A 的三格只读接口、4B 的两格 Debian 原生验收仍以其最新 CI 为准。容器扩展交付原设计中的建议，build/rollout NOT_RUN；Node 扩展只覆盖明确列出的 Debian 运行时版本规则，npm/其他来源 UNKNOWN。

仍须完成：受控启动/收据四格验收，精确维护策略与完整执行准入、实际 Ubuntu PHP 升级和失败闭环，以及 Debian PHP 修复的独立认证。公开 package apply 仍禁用，不得把已存在底层能力或检查点提交称为全部功能完成。用户已授权继续直到原设计四阶段完成；不需重新询问范围。
