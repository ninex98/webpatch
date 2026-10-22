# CI 基线验收 / CI baseline acceptance

2026-10-22；源码提交 `6baf70cdd18f1dbd238d5f9f12c9de6b8f05ea2f`。

[Actions 39736450120](https://github.com/ninex98/webpatch/actions/runs/39736450120)：9/9 jobs PASS。
本地 Python 3.10：140 passed；CI Python 3.10/3.12：各 140 passed。
Ubuntu 22.04/24.04 × FPM/mod_php：四格 amd64 GitHub 托管临时 VM PASS；安装 .deb、启动 systemd 服务并核对扫描前后 PID、APT/dpkg/PHP/Apache 配置状态不变。
Ubuntu 22.04/24.04、Debian 12 的 amd64 Docker：全部 PASS。

命令：`git push -u origin main`、`gh run view 39736450120 --json ...`、`gh run download 39736450120`。日志、JUnit、扫描及计划报告见 artifacts；源码和所有下载制品 SHA256 见 manifest.json。二进制安装包仅保留摘要，未提交 Git。

这些证据只证明此提交的安装、只读与服务冒烟行为；没有证明包密码学来源、完整路由或运行时安全。后续实现须重新测试。历史 phase-1.md 的 NOT_RUN 保留为历史事实，本记录补齐该门禁。
