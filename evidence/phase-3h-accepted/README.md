# 已安装公开 CLI 验收 / Installed public CLI acceptance

源码 `ba5d9f67dcebd9f527a24ff42bd67e3aaa4fbcf4`，Actions [39885894353](https://github.com/ninex98/webpatch/actions/runs/39885894353)。Ubuntu 22.04/24.04 × FPM/mod_php 与独立 Debian 12/13 × FPM/mod_php **八格服务 job 全部 PASS**。

每格成功路径从 / 调用已安装 /usr/bin/webpatch apply，经过具体 hash 确认、持锁复核、真实同分支包更新、全部服务新实例/只读视图/显式请求验证，返回 VERIFIED_WITHIN_DECLARED_SCOPE 且 safe=false。错误确认和同一计划重复调用均拒绝。每格第二次实际更新后通过显式注入的内部故障能力造成真实 HTTP 失败，结果 PARTIAL、changed=true；生产 CLI 没有故障参数。

lifecycle-results.json 是 16 次最终事务的字段摘录；all-attempts.json 包含所有尝试（包括被正确阻断的安装前观察竞争）。原始审计、日志、执行入口记录、错误/重复确认、环境与源码清单保留；validation.json 保存全部下载制品 SHA256、精确受测源码和留存映射。大型重复模型、客体串口日志与二进制包未加入 Git，均保留原摘要。

Validation: eight service job conclusions, sixteen final states, wrong/repeat rejection and installed-entry markers checked. Current implementation files match the tested source at evidence collection. Python 3.10/3.12 each 617 tests passed in the same run.

整轮为 15/17：Ubuntu 最小镜像过滤文档导致两格容器 FAIL，失败和修正见 phase-packaging-docs，不把它们算通过；后续完整矩阵另行验收。本记录不包含生产修复、任意路由/未来任务安全、自动回滚或 npm/第三方源支持。
