# 已完成四阶段后的维护交接 / Maintenance after four-phase completion

项目 `/Users/ninex/Projects/hll-ecosystem/apps/webpatch`，仓库 ninex98/webpatch。先读取 AGENTS.md、docs/design.md、README.md、docs/development-status.md 和 evidence/final-acceptance/README.md，再检查实际 Git/远端/Actions 与未提交工作。

用户要求的原设计四阶段已按有限支持范围完成；Debian、Node.js 和容器重建建议分别验收。最新功能/测试/CI 源码 941040c，Actions 39888070774 为 17/17 PASS：Python 3.10/3.12 各 617 tests、三格包/只读/建议容器、两格 Node、两格 Debian 归档、四格 Ubuntu VM 和四格 Debian QEMU 客体。后续文档/证据提交不改变受测实现；精确摘要、JUnit、环境、全部尝试和失败留存见最终证据。不要重新实现 2D/3A，也不要把历史待验收文字当当前进度。

公开 apply 已启用，但只接受 schema 5 managed review 和具体 plan hash；完整证据、持锁重新审阅、类型化包操作、运行时/请求验证和审计不可绕过。诊断计划仍 schema 4、不可执行。报告 schema 2、collector 协议 3；旧 collector/收据必须重新生成。八格成功路径已通过安装后 /usr/bin/webpatch CLI，健康故障能力仅显式注入测试。

## 后续工作原则

- 当前无未完成的四阶段必需验收；新增范围依用户后续任务实施。自动镜像发布、npm 修复、公开 APT 仓库/正式 Release 不属于已完成交付。
- 默认 scan 只读、不执行 PHP/Node、不发 HTTP、不刷新/下载。显式探针、准备和包操作有独立能力及确认边界；不把开发授权等同于生产修复授权。
- 不修改开发宿主 PHP/APT/系统包/服务；安装/服务测试仅 disposable 容器、GitHub hosted VM 或独立 Debian 客体，无 privileged 或宿主 root/proc/socket 挂载，不使用漏洞利用。
- 每个新独立阶段先明确范围/验收，保留日志/JUnit、环境、源码/制品摘要，然后立即中英双语提交。允许正常推送和 Actions，不强推或重写历史，保留无关用户工作。
- 不使用历史证据认证变化后的实现。需要远端验收可提交 CI_PENDING 检查点，失败后续修正，所有必需门禁通过才完成。
- 全局 safe=false。未知消费者/配置/来源/实例继续阻断；无自动回滚，不复用已尝试计划。CI 的有限新计划重试仅针对未变更的明确观察竞争，每次保留，产品无此能力。
- PHP/Node 规则到期时间 2026-10-29 00:00 UTC；到期重新查阅官方来源，禁止只延长日期。
