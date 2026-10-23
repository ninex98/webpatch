# 连续四阶段开发交接 / Continuous four-phase handoff

继续 `/Users/ninex/Projects/hll-ecosystem/apps/webpatch`，仓库 ninex98/webpatch。完整阅读 AGENTS.md、docs/design.md、README.md、docs/development-status.md、docs/phase-3.md、docs/phase-4.md，以及最新阶段证据。先核对工作区/远端/Actions，不将历史验收当当前证明。

用户已明确要求“继续直到所有功能全部完成”，并确认“按原设计四阶段推进，各扩展单独验收”。不要重做阶段 2D，也不再重复询问扩展范围。原阶段四交付为容器重建**建议**、独立 Debian 修复、Node.js adapter/rules；不包含自动镜像发布、npm 修复、公开签名 APT 仓库或正式 Release。

## 当前工作

源码已实现报告 schema 2、诊断计划 schema 4，以及 wrapper schema 1 / Plan schema 5 的受控修复审阅、持锁事务与修复后验证。公共 apply 由 release_gate.PUBLIC_REPAIR_ENABLED=false 禁用，不能通过环境、JSON 或 --yes 绕过。内核凭据 collector 协议 3；旧 collector/收据需重新准备。

最近 `4c53acc` 本地 605 PASS，Actions 39881542701 为 13/17 PASS，剩余 Ubuntu 24.04 两格持锁复核失败，以及 Debian 12/13 Apache 夹具重装后保留旧 deleted 模块。`2d8132c` 补充复核诊断及夹具显式重启；Actions 39883475413 待验收，证据 evidence/phase-3g4。先查看更新后的实际 CI，按失败证据修正，不放宽 UNKNOWN。

Ubuntu 22.04 两格和 Debian 两版 FPM 已实际验证 base→fixed 升级及重启后 HTTP 失败。仍须完整八格当前源码通过，保存独立证据，再开放严格确认入口并在安装后的公开 CLI 验证。最后同步文档/包说明/当前状态。容器建议和 Node 两格已在829df71基线及后续运行通过，Debian 归档链也独立通过；完整支持按最新 CI 判断。

## 持续约束

- 默认 scan 只读、不执行 PHP/Node、不发 HTTP、不刷新/下载。显式探针和准备有独立能力及确认边界。
- 不修改开发宿主 PHP/APT/系统包/服务，不访问生产目标修复；实际安装/服务测试仅 disposable 容器或 GitHub hosted VM/独立 Debian 客体，无 privileged 或宿主 root/proc/socket 挂载。
- 每个独立小阶段先定范围与验收，保存日志/JUnit、环境及源码/制品摘要，立即提交。标题和正文均中文+英文。允许正常推送和 Actions；不强推、不重写远端历史，保留无关工作。
- 原生检查依赖推送时可提交明确 CI_PENDING 检查点；失败后续修正，所有必需门禁通过才宣布完成。不要为消除 diff 空白警告改写原始日志。
- 全局 safe=false；有限声明范围的验证不代表任意未来任务、隐藏实例、匿名代码或历史入侵不存在。不自动回滚或重试同一计划。
- PHP/Node 规则至 2026-10-29 00:00 UTC，过期重新查阅官方来源，禁止只延长日期；不用真实漏洞利用。
