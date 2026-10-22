# 下一轮开发交接：阶段三前置接口 / Next development handoff

继续开发 `/Users/ninex/Projects/hll-ecosystem/apps/webpatch`（`ninex98/webpatch`）。先完整读取 AGENTS.md、docs/design.md、README.md、docs/development-status.md、docs/phase-2d.md，以及 evidence/phase-2d4/README.md、current-source-validation.json 和 accepted-ci/run.json。检查当前 Git/远端/Actions 与未提交工作，不把历史记录当当前验收。

## 当前基线

阶段 2D 已实现结构化覆盖/作用域、运行文件和标准 PHP 模块证据、FPM UNIX listener 与静态 pool/handler 候选关系、统一计划门禁及有效期/漂移核对。最终报告 schema 2，计划 schema 4；旧计划必须重新扫描。有限诊断输入可以 READY_FOR_REVIEW，但执行准入始终 BLOCKED，apply 拒绝。准确源码与 CI 结果以 current-source-validation.json 为准。

首次 2D.2 四格 VM 因保存计划超过普通 1 MiB 文本读取限制失败，完整失败记录在 evidence/phase-2d2/first-ci。现有独立 16 MiB 计划读取接口，不放宽配置/procfs 限制。不要重新搭建或重复实现 2D.1。

## 下一步必须先闭合的契约

仍位于原阶段二末尾/阶段三前置接口，不是可自动修复产品。先实现一个独立可验收的 3A 小阶段：明确部署清单与显式应用证据接口及其验证规则。不得仅凭调用者声明把 UNKNOWN 改成 PASS。

- 作用域与消费者：明确操作者审阅的 host/container/boot 范围；对共享包的全部服务、CLI 任务、pool 和自定义安装逐项核对。缺失/未识别消费者继续阻断。
- 加载配置与请求归属：设计独立、显式选择、无副作用的证据/探针能力；绑定 scope、boot、PID、starttime、执行映像、相关模块、配置摘要、请求上下文、采集时间和到期时间。必须验证信任来源和防重放/状态漂移。静态文件、mtime、监听 socket、HTTP 200、普通标记页都不是实例归属证明。先在四格 disposable VM 证明有限范围；默认 scan 仍不执行配置脚本、不写诊断页、不发请求。
- 后续执行条件：完整且获批的依赖变化、候选维护脚本/triggers/conffile 行为、所有受影响实例的停机预算、plan hash 显式确认、持锁事务前重查、执行后运行时/路由/健康验证和失败审计。APT 不保证事务回滚。

本交接不授权直接跳过这些门禁接入实际修复。应先报告首个小阶段的范围/验收，然后实施、测试、留证并立即提交；后续执行器阶段须按原设计在隔离 VM 验证，生产目标仍须 reviewed dry-run 和显式确认。

## 持续约束

- 不修改开发宿主 PHP、APT、系统包或服务；不访问生产目标执行修复。安装/服务准备/故障注入仅用 disposable Docker 或 GitHub-hosted Ubuntu VM，禁止 privileged、自托管 runner 和宿主 root/proc/socket 挂载。
- 保持适配器、注入 I/O、证据、规则、规划、执行与验证解耦；严格 fake I/O 不回退宿主。UNKNOWN 可行动且阻断自动修复。
- 规则有效至 2026-10-29 00:00 UTC。若已过期或需要修改，重新查阅官方 PHP/Ubuntu/Debian 来源，记录 review/provenance/expiry；禁止仅延长日期。不用真实漏洞利用。
- 不顺带扩展 Node.js、Debian 修复、PPA/Sury、ESM、自动镜像重建、公开 APT 仓库或正式 Release。
- 复用项目虚拟环境、Git identity/auth/origin。允许正常推送和运行 Actions；不强推、不重写远端历史。保留无关用户工作。
- 每个独立小阶段先定验收条件，通过后立即 Git 提交；标题和正文都包含中文与英文，记录命令、PASS/FAIL/NOT_RUN/BLOCKED、当前源码/制品摘要与证据路径。云端必须先推送时，使用明确的 CI 待验收检查点；失败用后续提交修复，所有必要门禁通过后才宣布完成。

## 2026-10-23 用户新授权与活动进度（优先于上文旧的单轮范围）

用户明确要求“继续直到所有功能全部完成”，并确认“按原设计四阶段推进，各扩展单独验收”。因此阶段三完成后继续 Debian、Node.js 与容器重建范围，不受上文旧的“不顺带扩展”单轮限制；不把功能开发当作对开发宿主/生产系统执行修复或正式发布的授权。

已继续交付部署清单、显式内核凭据探针、候选维护内容审阅、事务状态机和全可见进程消费者 census。具体提交/实际 CI 见 docs/development-status.md 与 docs/phase-3.md，不重做 3A.1。当前重点为归档封存解析修正及 3D.2 受控启动/只读配置视图，后者如有未提交工作必须保留并继续验证。随后闭合实际准入/执行/修复后验证，再完成各扩展。保持每个独立小阶段先验收、立即双语提交、正常推送；所有 UNKNOWN 仍阻断自动修复。
