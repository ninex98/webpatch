# 连续四阶段开发交接 / Continuous four-phase handoff

继续 `/Users/ninex/Projects/hll-ecosystem/apps/webpatch`，仓库 ninex98/webpatch。完整阅读 AGENTS.md、docs/design.md、README.md、docs/development-status.md、docs/phase-3.md、docs/phase-4.md，以及最新阶段证据。先核对工作区/远端/Actions，不将历史验收当当前证明。

用户已明确要求“继续直到所有功能全部完成”，并确认“按原设计四阶段推进，各扩展单独验收”。不要重做阶段 2D，也不再重复询问扩展范围。原阶段四交付为容器重建**建议**、独立 Debian 修复、Node.js adapter/rules；不包含自动镜像发布、npm 修复、公开签名 APT 仓库或正式 Release。

## 当前工作

源码已实现报告 schema 2、诊断计划 schema 4，以及 wrapper schema 1 / Plan schema 5 的受控修复审阅、持锁事务与修复后验证。公共 apply 的维护者门禁现已开启；仍不能通过环境、JSON 或 --yes 绕过精确确认和证据门禁。内核凭据 collector 协议 3；旧 collector/收据需重新准备。

`2d8132c` 的 Actions 39883475413 已 17/17 PASS：两组 fixtures、三格包容器、两格 Node、两格 Debian 归档、四格 Ubuntu 和四格 Debian 独立生命周期。Ubuntu 实际升级/故障证据提交 c841096，Debian 独立留证 98a3071。

公共入口已根据该基线开放精确确认。最新增量把八格成功路径改为安装后的 /usr/bin/webpatch apply，从 / 运行并验证错误 hash、实际升级、结果/退出码和禁止复用。最终 CLI CI 尚待完成，先检查 Git/Actions 和 evidence/phase-3h-public。

d314ead 复验两格 Apache 在故障场景安装前遇到短命进程或模拟输入漂移，生产门禁正确阻断；CI 新增仅针对 changed=false 的明确观察竞争生成新计划，最多三次，每次留存。绝不放宽门禁、重试同一计划或重试已经 changed 的事务。完成新源码矩阵后收齐最终证据、文档/支持矩阵；不重做已验收阶段。

## 持续约束

- 默认 scan 只读、不执行 PHP/Node、不发 HTTP、不刷新/下载。显式探针和准备有独立能力及确认边界。
- 不修改开发宿主 PHP/APT/系统包/服务，不访问生产目标修复；实际安装/服务测试仅 disposable 容器或 GitHub hosted VM/独立 Debian 客体，无 privileged 或宿主 root/proc/socket 挂载。
- 每个独立小阶段先定范围与验收，保存日志/JUnit、环境及源码/制品摘要，立即提交。标题和正文均中文+英文。允许正常推送和 Actions；不强推、不重写远端历史，保留无关工作。
- 原生检查依赖推送时可提交明确 CI_PENDING 检查点；失败后续修正，所有必需门禁通过才宣布完成。不要为消除 diff 空白警告改写原始日志。
- 全局 safe=false；有限声明范围的验证不代表任意未来任务、隐藏实例、匿名代码或历史入侵不存在。不自动回滚或重试同一计划。
- PHP/Node 规则至 2026-10-29 00:00 UTC，过期重新查阅官方来源，禁止只延长日期；不用真实漏洞利用。
