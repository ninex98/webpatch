# Debian 客体导出修正 / Guest export correction

9212b8b/8e61800 客体已通过 QEMU 启动、SSH、源码校验和真实 PHP 安装。随后 build_deb.py 因导出包缺少 docs/design.md 失败；清理代码读取 root-owned qemu.pid 又触发 PermissionError。原客体日志附后。

导出纳入打包所需 docs/双语 README，并继续逐文件比对受测 commit 内容；PID 文件由已授权的临时 runner sudo 读取，清理竞态不再因读取失败掩盖原结果。不增加宿主文件共享或 privileged 容器。

本地 597 tests PASS 与编译/脚本语法检查 PASS；真实四格客体重验 CI pending。开发宿主未启动 QEMU、安装工具或修改服务。
