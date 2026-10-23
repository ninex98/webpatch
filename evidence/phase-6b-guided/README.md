# 阶段 6B：引导修复与 0.2.0 候选 / Guided repair and 0.2.0 candidate

2026-10-23. 本地检查 PASS；这是 CI_PENDING checkpoint，尚未宣布新版本原生验收或公开发布完成。

范围：`webpatch fix` 使用原有 planning/preparation/repair APIs，交互收集显式探针信息，自动保存私有审阅/收据；服务准备与包修复分别要求完整计划摘要。--dry-run 无探针请求/交互/文件写入；--review 可交互确认已有受控审阅。UNKNOWN/不支持环境/缺失归档仍阻断，原有持锁复核、到期、重放及后验检查不变。

验证：647 pytest PASS（含 16 项引导/会话测试及新增未知状态呈现反例），完整 JUnit/log 保留。Ubuntu 24.04 arm64 disposable 容器已安装 CLI 23 场景 PASS，包括安静/verbose 安装、完整失败回显、无 PHP 的 fix --dry-run 不创建状态目录。默认无 PHP 中英文/宽窄输出在前阶段验证；本阶段用新安装包非 root 的真实终端输出重新生成 README 示例（terminal-capture.json）。shell/diff/actionlint/SVG/XML/本地链接检查 PASS。源码/制品和环境在 manifest.json。

原生门禁：原八格真实修复成功分支将通过 pseudo-terminal 调用已安装 `fix --review`，输入精确 hash、测试错误确认与重放；故障注入仍在显式内部测试能力，不能从产品 CLI 开启。此 checkpoint 的 hosted CI 尚未运行，不将 fixture 成功当作实际修复证明。默认向导的服务准备使用原已认证 API；新增 orchestration 的准备/取消路径有隔离 unit fixtures，完整默认无参数向导的原生部署探针流程 NOT_RUN。向导明确要求已部署探针，不自动创建 Web 页面。

当前主分支/PR/手动运行仍完整执行 17 个安全 job。发布门禁已要求同一 main SHA 通过，新增 tag 不再重复运行相同矩阵。检查现状时发现历史 v0.1.0 tag 重跑 39895095284 的一个 Apache profile 在准备后因消费者/输入漂移阻断；原失败日志保留为 prior-v0.1.0-tag-failure.log，不删除或改写旧结果，也不放宽产品准入。

会话目录 root-private，文档 O_EXCL/O_NOFOLLOW/0600，不覆盖已保存文件。初始确认前不创建会话；准备后取消明确保留 changed=true 和恢复收据。终端控制/Bidi 转义、JSON/退出码兼容仍受测。开发宿主 PHP/APT/服务未修改，包和服务测试只在隔离容器或后续 hosted VM 中执行。
