# 临时 VM 的 dpkg hook / Hosted fixture dpkg hook

509f83c 的真实 noble/fpm 审计 FAIL：预装 runner 含 `/etc/dpkg/dpkg.cfg.d/needrestart` post-invoke 特殊配置。产品按要求阻断，没有忽略 hook 或宣称 PASS。原始日志见本目录。

修正只在 GitHub-hosted VM 基线准备时保存该文件哈希并移至临时备份，再建立无特殊 dpkg hook 的正例配置；scan/plan 的只读不变检查在此之后开始。其他 hook 仍阻断。宿主未改动。该脚本没有用于生产修复。

本地隔离暂存源码测试/JUnit/摘要见本目录；bash -n PASS。真实四格重验 CI pending。
