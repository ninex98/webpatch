# 阶段 2D 接口与验收 / Phase 2D contracts

当前接口为报告 schema 2、计划 schema 4；下文按小阶段记录，早期计划 schema 3 已被 2D.3 替代。最终验收见 evidence/phase-2d4/current-source-validation.json。

## 2D.1 覆盖和作用域

报告 schema 从 1 升至 2：原字段、coverage_gaps 字符串、safe=false 和退出码语义保留，新增 inventory.coverage 与 scan_scope。覆盖项包含稳定 ID、requirement、status、subjects(kind/id)、evidence_ids、reason、next_step 和 blocks_repair。VERIFIED 只证明该项命名的局部关系；OBSERVED 是文件/元数据观察；UNKNOWN 是缺失或冲突的证据；UNSUPPORTED 是超出支持范围；NOT_CHECKED 是适配器未执行。未知、观察和未检查项不授予执行权限。空清单仍是 UNKNOWN，扫描没有完整性证明。

运行实例 ID 由扫描作用域摘要、PID、starttime 组成。包、服务、pool、route、文件和自定义安装具有独立实体引用。安装文件认证与运行实例关联独立呈现；每个包的观察到的消费者均列出，未观察消费者不会被宣称不存在。多分支和 CLI/FPM 包分别保留。

计划 schema 从 2 升至 3，新增 scope 与 coverage。可用 `webpatch plan --dry-run --target-package php8.1-fpm:amd64 --format json` 选择一个或多个包。目标选择不缩小扫描范围：scope 中保留全部观察到的运行实例、未解决实例、每个受影响包的所有已关联进程/服务，以及依赖变化涉及的包。影响范围 completeness 继续 UNKNOWN，不能用选择绕过其他实例缺口。

迁移：读取报告的消费者可继续读取旧字段，但应按 schema 2 使用结构化覆盖；旧 schema 2 计划不能补字段后执行或验证为新计划，verify-plan 返回 PLAN_SCHEMA_RESCAN_REQUIRED，必须重新扫描/生成 schema 3 计划并重新审阅。验证结果依旧 BLOCKED、executable=false、退出码 4。所有 apply 调用继续拒绝。

本小阶段不增加运行时证明能力；映射/配置/路由连接及统一计划门禁分别在 2D.2/2D.3。静态文件、包认证、局部关联均不代表运行时安全。

## 2D.2 运行文件、监听端点与静态路由

RuntimeInstance 增加 files、endpoints、mapping_sha256、namespace_sha256 和各自观察状态。files 将主映像和标准 `/usr/lib/php/` / `libphp*.so` 映射分开，记录 device/inode/sha256、包引用与证据。文件认证要求稳定映像/映射与受信任归档中的路径及字节相符；不认证进程内存，也不穷举自定义扩展或所有原生依赖。Apache 主程序本身不在 PHP 归档身份链内，明确保持 UNKNOWN。

FPM 的 UNIX socket 关联同时检查进程 fd 所持 inode、该进程网络命名空间的 UNIX 表、监听标记/类型/状态和重复读取一致性。TCP listener、外部网络命名空间及不可读 fd 仍 UNKNOWN。socket 所属进程证明不等于 pool 名称已加载。

配置树只解析有限静态 include，观察 pool/handler 并关联服务与候选进程；所有关系保留 CONFIGURED 状态。条件块、重复/动态 listener、未解析 include、扫描中配置变化均有缺口。加载配置 UNKNOWN，请求归属 NOT_CHECKED。默认不执行 PHP/FPM/Apache 配置、不部署诊断页面、不发 HTTP 请求。现有 VM 普通标记页仍只验证测试环境行为，不输入归属判定。

计划重查 namespace/root、进程 starttime、映像身份、PHP 映射摘要和已观察 listener。对证据变化的检测不是并发锁或内存完整性证明。纯只读证据无法解除 loaded configuration / request attribution 门禁。

真实环境验收新增实际映射文件删除/替换的无害 mmap helper，以及修改配置但不重启服务的反例；只在 GitHub-hosted 临时 VM 中运行并恢复配置。此处的无害映射数据不是漏洞二进制或真实漏洞利用。

## 2D.3 统一审阅门禁

最终计划 schema 为 **4**（替代 2D.1/2D.2 的 schema 3）；旧 schema 2/3 的保存计划统一返回 PLAN_SCHEMA_RESCAN_REQUIRED，须重新扫描和审阅。报告 schema 仍为 2，退出码不变。

`gates` 将规则、目标选择、源策略、签名链/文件身份、每个实体覆盖要求、依赖变化、pin/hold/dpkg、特殊 APT 配置、锁、状态稳定性、证据时效、模拟、安装等价性、维护脚本/conffile、预计中断和执行授权分开。每项有稳定 ID、实体、证据 ID、原因和解除要求。PASS 只属于该项；UNKNOWN/NOT_RUN/UNSUPPORTED/BLOCKED 均加入阻断项。

`review_status=READY_FOR_REVIEW` 表示目标和诊断依赖解析等基本输入齐全，可开始人工审阅；不是执行准入。已有合法 fixture 能获得多个 PASS，故不是恒定拒绝代替判断。安装等价性、维护脚本/conffile、停机预算、覆盖及加载/请求证明仍阻断。`admission_status=BLOCKED`、`executable=false`，没有安装或重启执行器。

计划保存 `scan_evidence`（e 前缀）和规划 `evidence`（p 前缀），门禁引用可在文档内解析。最大有效期为生成时间+30分钟、扫描时间+30分钟、规则到期、全部已认证索引 Date+7天/Valid-Until 的最早值；base pocket 仍不能成为新鲜修复候选。索引过期、反向时钟、目标/依赖/作用域/配置/运行状态变化都会拒绝；重新计算摘要不能掩盖语义门禁篡改或延长有效期。摘要不是签名或授权证明。

保存计划有独立 16 MiB 有界读取接口；普通配置/procfs 文本仍限 1 MiB。该调整修正首次 2D.2 VM 中合法证据计划约 1.4 MiB 导致 verify-plan 读取失败的问题，不放宽目标配置读取边界。

阶段三必须先实现：按具体 plan hash 的显式确认；受信任、过期受限且绑定 scope/boot/PID/starttime/映像/模块的加载配置与请求证据接口；已批准的完整依赖/维护脚本/conffile 行为；所有消费者的停机预算；锁和事务前复核；修复后进程/路由/健康验证及失败审计。未来探针必须显式选择、无副作用，并证明请求归属到上述实例；普通标记/HTTP 200、监听 socket 或配置 mtime 都不符合接口。当前没有外部声明直接解除门禁的输入入口。
