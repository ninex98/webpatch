# 2D.2 运行实例与路由证据 / Runtime and route evidence

本地 PASS：322 tests，日志/JUnit 和对应源码哈希见本目录；`bash -n scripts/ci_vm_smoke.sh`、`git diff --check` PASS。

实现标准 PHP 主映像/模块逐文件身份、FPM UNIX listener 归属、pool/静态 handler 的候选关联；命名空间、映射、socket 和配置变化可拒绝。加载配置和请求归属仍 UNKNOWN/NOT_CHECKED。新增测试覆盖认证字节正例、模块权限/删除/替换/未知包、监听 fd/namespace/状态变化、多个 pool/socket 和 Apache 条件配置。

CI 待验收 / CI pending：四格 Ubuntu VM 与三格 Docker 必须在推送后运行；此检查点不宣称 2D.2 真实环境已通过。VM 新增无害 mmap 删除/替换与配置修改反例，扫描不执行诊断请求。详细限制见 docs/phase-2d.md；实际修复 NOT_RUN_DISABLED。
