# 公开严格确认入口 / Strict public repair entry

前置认证：2d8132c、Actions 39883475413 全部 17/17 PASS，内部 Ubuntu/Debian 各四格真实升级/故障已留证于 phase-3g-accepted 和 phase-4c-accepted。维护者发布门禁现开启，公共 apply 仍要求 schema 5 managed review、精确确认、持锁重新审阅和后验验证；没有无人确认、--yes 或环境绕过。

本地 617 tests PASS（含畸形状态目录在 native capability 构造前拒绝，以及只允许未变更观察竞争生成新夹具计划的反例）。最终原生 CLI 矩阵 CI_PENDING。八格成功路径将调用安装后 /usr/bin/webpatch，从 / 运行，核对确认、实际升级、JSON/退出码和同计划重复拒绝。故障能力只显式注入测试，不成为 CLI 参数。

d314ead 的两格 Apache 故障场景在安装前遇到短命进程/模拟输入竞争，原日志和结果摘录保存在本目录；两格成功升级场景通过。CI 最多三份新计划，仅当 changed=false 且明确为观察竞争；保留每次 review/result，不重试已变更事务或原计划。产品继续严格阻断，不包含该重试功能。

Validation: logs/JUnit, source/artifact hashes, diff checks. Native installed CLI and added packaged-document byte checks remain pending until this source passes. No developer-host or production package/service change; no exploit or automatic rollback. Success stays scoped with safe=false.
