# 完整测试基线 / Complete hosted baseline

1db0afb 的 jammy/fpm 执行输入审计正确 FAIL 于 pkg-config-hook-config 和 pkgconf-hook-config 特殊 dpkg 配置。此前只移走 needrestart 不足；原始日志在本目录。

临时 VM 在全部安装准备结束后、只读基线之前逐个保存特殊 dpkg 配置哈希并移至私有临时备份；保留 no-debsig/default log 普通选项。快照同时加入 /etc/dpkg，使后续审计期间的配置修改能被检测。产品审计规则没有改变，未经审阅 hook 仍阻断；这只是明确的有限正例环境。

本地源码测试与 bash -n 结果见本目录；云端重验 CI pending。宿主未改动。
