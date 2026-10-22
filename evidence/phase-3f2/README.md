# 3F.2 统一修复审阅 / Managed repair review

本地 534 tests PASS，新增12项：完整合同绑定、精确确认、无变更不执行、缺少启动证据、额外消费者、未知 archive、脚本更改、特殊 hook、目标 diversion、预依赖变化/复杂表达式和 fake I/O 无回退。

READY_FOR_CONFIRMATION 测试使用明确注入的启动事实（签名/真实挂载/内核请求由独立测试验证），不冒充 VM 修复。其余归档、脚本、源、依赖、消费者和门禁由实际 fixture I/O 核对。公开 apply 仍禁用。

CI pending：四格 VM 原只读检查之后建立显式 plain APT 维护 fixture，并核对当前官方 cohort/handler 归档与 NO_PACKAGE_CHANGES 的真实计划。这个检查不是旧→新升级；实际修复/故障闭环仍待执行器阶段。源码哈希、日志/JUnit 在本目录。
