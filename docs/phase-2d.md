# 阶段 2D 接口与验收 / Phase 2D contracts

## 2D.1 覆盖和作用域

报告 schema 从 1 升至 2：原字段、coverage_gaps 字符串、safe=false 和退出码语义保留，新增 inventory.coverage 与 scan_scope。覆盖项包含稳定 ID、requirement、status、subjects(kind/id)、evidence_ids、reason、next_step 和 blocks_repair。VERIFIED 只证明该项命名的局部关系；OBSERVED 是文件/元数据观察；UNKNOWN 是缺失或冲突的证据；UNSUPPORTED 是超出支持范围；NOT_CHECKED 是适配器未执行。未知、观察和未检查项不授予执行权限。空清单仍是 UNKNOWN，扫描没有完整性证明。

运行实例 ID 由扫描作用域摘要、PID、starttime 组成。包、服务、pool、route、文件和自定义安装具有独立实体引用。安装文件认证与运行实例关联独立呈现；每个包的观察到的消费者均列出，未观察消费者不会被宣称不存在。多分支和 CLI/FPM 包分别保留。

计划 schema 从 2 升至 3，新增 scope 与 coverage。可用 `webpatch plan --dry-run --target-package php8.1-fpm:amd64 --format json` 选择一个或多个包。目标选择不缩小扫描范围：scope 中保留全部观察到的运行实例、未解决实例、每个受影响包的所有已关联进程/服务，以及依赖变化涉及的包。影响范围 completeness 继续 UNKNOWN，不能用选择绕过其他实例缺口。

迁移：读取报告的消费者可继续读取旧字段，但应按 schema 2 使用结构化覆盖；旧 schema 2 计划不能补字段后执行或验证为新计划，verify-plan 返回 PLAN_SCHEMA_RESCAN_REQUIRED，必须重新扫描/生成 schema 3 计划并重新审阅。验证结果依旧 BLOCKED、executable=false、退出码 4。所有 apply 调用继续拒绝。

本小阶段不增加运行时证明能力；映射/配置/路由连接及统一计划门禁分别在 2D.2/2D.3。静态文件、包认证、局部关联均不代表运行时安全。
