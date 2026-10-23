# WebPatch 0.2.0 — Clear results and guided repair / 清晰结果与引导修复

默认扫描改为分层摘要：结论、可能受影响的包、待核实项和下一步。支持中文/英文、自动终端颜色、NO_COLOR 和 --details；JSON 与退出码保持兼容。安装器收敛成功日志，修复 _apt 读取公开 deb 的权限问题，失败仍显示完整错误。

Default scans now show a readable result, affected packages, remaining checks and next steps. English/Chinese output, terminal colors and --details are available; JSON and scan exit codes remain compatible. Installation shows concise progress and retains complete failure diagnostics.

`sudo webpatch fix` guides preparation and package repair using the existing supported profiles, manages review files/receipts, and requires the complete displayed plan hash for each change. Existing probes and authenticated package archives remain prerequisites. Missing evidence blocks repair; no --yes, automatic probe deployment or hidden service action is added. Cancelling after preparation does not undo service changes; recovery receipts are retained.

Supported install targets: Ubuntu 22.04/24.04 and Debian 12/13. Confirmed repairs remain limited to official amd64 PHP FPM/mod_php profiles. Other systems/architectures and container in-place repair remain unsupported. All safety results retain safe=false; installation does not establish runtime safety.

Rules still expire at **2026-10-29 00:00 UTC**; this release does not extend their validity. Upgrade by running the installation command again. Old preparation receipts/plans bind implementation hashes and must be regenerated after a program update.
