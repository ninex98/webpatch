# 2D.4 当前源码真实环境验收 / Current-source environment acceptance

本地 PASS：336 tests；`bash -n scripts/ci_vm_smoke.sh` 与 `git diff --check` PASS。源码/平台、日志与 JUnit 摘要见 manifest.json。

CI 待验收 / CI pending：复用原 Python 3.10/3.12、三个只读禁网 Docker 和 Ubuntu 22.04/24.04 × FPM/mod_php 四格。新增第二个 FPM pool/socket、逐门禁状态/证据引用断言、实际模块删除/替换及配置漂移、普通用户权限缺口；比较扫描/模拟前后所有相关 PHP/Apache PID/starttime 与配置/APT/dpkg 状态。没有 WebPatch 安装/重启执行器。

本检查点仅完成本地验收；云端结果需与本次源码 SHA256 对应后才能宣布完成。2D.2 首轮失败（计划文件读取上限）及后续重跑都保留，不能替换成旧阶段通过记录。
