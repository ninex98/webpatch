# 开发状态 / Development status

核对日期：2026-10-23（Asia/Shanghai）。这是连续四阶段开发任务；用户已确认 Debian、Node.js 和容器重建扩展分别验收。当前公开 `apply` 仍禁用；不能将内部事务实现等同于完整发布验收。

## 当前进度

| 原设计阶段 | 已实现范围 | 验收状态 |
|---|---|---|
| 1 只读基础 | 注入 I/O、发现/规则/模型、CLI、打包 | 已完成；历史证据在 evidence/phase-1 及后续矩阵 |
| 2 可信发现与 dry-run | 实例/文件/来源/路由证据、结构化覆盖、APT 模拟、不可变诊断计划 | 2D 的 efb122d、Actions 39763873264 为 9/9 PASS；[证据](../evidence/phase-2d4/README.md) |
| 3 有限 Ubuntu 修复 | 内核请求绑定、只读配置视图、全 task FD census、精确维护合同、持锁事务、修复后验证/审计 | 已实现，完整真实矩阵待验收；公开入口受发布门禁禁用 |
| 4A 容器 | image digest 声明、逐 CVE 重建建议 | 三格只读/禁网容器独立验证；不构建/推送/发布 |
| 4B Node.js | 独立 adapter/rules，Debian 12/13 两项运行时 CVE | 两格独立原生容器通过；无 npm 审计或 Node 修复 |
| 4C Debian PHP | 独立签名根、归档链、精确 profile、准备/事务 | Debian 12/13 归档认证与 FPM/Apache 四格内部生命周期分别通过；[独立证据](../evidence/phase-4c-accepted/README.md) |

## 最新源码与 CI

- `4c53acc`：605 本地 tests PASS；[Actions 39881542701](https://github.com/ninex98/webpatch/actions/runs/39881542701) 为 **13/17 PASS，4 FAIL**。Ubuntu 22.04 两种 SAPI、Debian 12/13 FPM 的实际升级和健康故障路径通过；不是全矩阵验收。
- 两项 Debian Apache 在重装测试包后仍映射 deleted 旧模块，生产门禁正确阻断；两项 Ubuntu 24.04 在持锁复核时拒绝，尚缺精确差异诊断。
- `2d8132c`：本地 605 PASS，补充复核变化字段/阻断原因并重启重装后的 Apache 测试基线；[Actions 39883475413](https://github.com/ninex98/webpatch/actions/runs/39883475413) **CI_PENDING**。失败原日志、JUnit 和源码摘要在 [phase-3g4](../evidence/phase-3g4/README.md)。
- `2d8132c` 的六个 Debian job 已独立 PASS，见 [phase-4c-accepted](../evidence/phase-4c-accepted/README.md)；同轮 Ubuntu 尚在运行，不声明整轮通过。
- 公共入口准备 `4c53acc` 的证据在 [phase-3h-entry](../evidence/phase-3h-entry/README.md)。启用入口仍须全部要求的原生升级/故障验证通过，并验证安装后的公开 CLI。

历史已接受基线 `829df71` / [39848034144](https://github.com/ninex98/webpatch/actions/runs/39848034144) 为 **11/11 PASS**：Python 3.10/3.12 各 522，四格受控准备/收据、三格包能力/只读容器、两格 Node。[完整证据](../evidence/accepted-829df71/README.md) 只适用于该源码，不认证其后新增执行器。原生合成包操作独立证据在 [phase-3e2](../evidence/phase-3e2/accepted-native/README.md)。

## 支持边界与接口

报告 schema 2、诊断计划 schema 4；`repair-plan` 的 wrapper schema 1 内含 schema 5 Plan。诊断 READY_FOR_REVIEW 不允许执行；受控 READY_FOR_CONFIRMATION 必须具体 hash 确认、持锁重新验证。所有结果保留 safe=false，成功仅为 VERIFIED_WITHIN_DECLARED_SCOPE。

有限修复 profile：Ubuntu 22.04/php8.1、24.04/php8.3、Debian 12/php8.2、13/php8.4，官方同分支 amd64、标准 FPM/mod_php、完整已安装 PHP source cohort。未知消费者/实例、特殊 APT/dpkg 配置、依赖变更、复杂预依赖、其他架构/源/分支保持阻断。不支持 PPA/Sury/ESM、自编译、CGI/FrankenPHP/LiteSpeed、容器原地修复或任意站点认证。

collector 协议 3；只能接受两项已审阅默认 INI 指令的新增，既有设置变化仍阻断，详见 [阶段三](phase-3.md)。规则到期时间保持 **2026-10-29 00:00 UTC**；到期须重新审阅官方来源，不得只延长日期。

测试安装/服务变更只在 disposable 容器、GitHub hosted Ubuntu VM 和独立 Debian QEMU 客体中发生。开发宿主 PHP/APT/服务未修改。没有漏洞利用、生产修复、公开签名仓库或正式 Release。原有双语 README/SVG 工作由 `13c6c9c` 保存，后续保留视觉资源。

## 剩余验收

完成四格 Ubuntu 与四格 Debian 实际升级/故障闭环；保存当前源码的完整成功/失败证据；启用并原生验证严格确认入口；同步最终支持矩阵与交接文档。每个独立阶段继续先定范围、测试留证、立即双语提交并正常推送；不得将 NOT_RUN/BLOCKED 写成 PASS。
