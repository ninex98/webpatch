# 阶段 2A / Runtime association — CI 待验收 / pending

范围：进程启动标识、文件 device/inode/SHA256、包所有者、systemd cgroup/服务、FPM pools、mod_php 已加载映射和静态 Web handler 观察。进程开始/结束及文件二次读取检查变化；不同 PID namespace/chroot 不关联宿主包。systemd PrivateTmp 的单独 mount namespace 只有在同 root、PID namespace、live unit 和文件视图一致时才可关联。

本地验收：Python 3.10，165 tests PASS；`bash -n scripts/ci_vm_smoke.sh` PASS；日志、JUnit、源码摘要同目录。CI 必须运行此源码的四格 VM 正向服务关联、无副作用 HTTP 标记响应和扫描前后状态检查，以及完整 fixture/Docker 矩阵。当前 CI NOT_RUN，不宣布阶段完成。

限制：VERIFIED_LOCAL_ASSOCIATION 是本地身份关联，不是厂商字节认证或补丁加载证明。静态 pools/routes 不是已加载配置或实际应用路由证明；动态 includes、站点覆盖、.htaccess、未知/自定义安装、CGI 等保留 UNKNOWN。配置关系不会解除自动规划门禁。没有任何实际修复执行能力。
