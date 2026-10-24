# WebPatch 0.3.0 — Docker discovery / Docker 自动发现

在宿主机运行 `webpatch scan --lang zh`，现在会自动发现一个本机 Docker 实例，并逐个列出容器名、镜像、PHP 软件包、常见安装路径、头文件版本和进程线索。无需在容器中安装 WebPatch。权限拒绝、容器停止、读取失败和覆盖限额都有具体说明及下一步；宿主机空清单不再掩盖容器结果。

Running `webpatch scan` on the host now discovers one local Docker daemon and reports each container's image, PHP packages, conventional installation paths, header versions and process hints. No WebPatch installation inside containers is required. Access failures, stopped containers, read errors and coverage limits have explicit next steps.

Scans use bounded local GET/HEAD requests. They do not exec commands in containers, install software or restart services. Use `--docker-socket /absolute/path` for a custom/rootless Unix socket or `--docker off` for the original current-system scope. Remote contexts, other daemons, Kubernetes/containerd and arbitrary custom paths are not automatically covered.

Ubuntu/Debian package versions reuse the existing reviewed vendor rules. Alpine and custom PHP installations remain UNKNOWN; header versions, image names and successful reads do not authenticate running code or patch provenance. Host and container inventories remain separate. A potentially affected container package produces scan exit 1; other incomplete evidence remains exit 2 / UNKNOWN. All safe fields remain false. Containers must be updated through their image/build/deployment workflow; no in-place container repair is added.

Supported installer targets remain Ubuntu 22.04/24.04 and Debian 12/13. Confirmed host repairs retain the existing official amd64 PHP FPM/mod_php prerequisites and exact confirmation. Existing plans/receipts bind implementation hashes and must be regenerated after an upgrade.

再次运行 README 中的安装命令即可升级，确认 `webpatch --version` 显示 `0.3.0`，再执行 `webpatch scan --lang zh`。默认只检查一个本机 Docker daemon；需要有访问该 socket 的权限。

Rules still expire at **2026-10-29 00:00 UTC**. This release does not change risk rules or extend their validity.
