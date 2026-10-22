# 阶段 2A / Runtime association — CI 待验收 / pending

范围：进程启动标识、文件 device/inode/SHA256、包所有者、systemd cgroup/服务、FPM pools、mod_php 已加载映射和静态 Web handler 观察。进程开始/结束及文件二次读取检查变化；不同 PID namespace/chroot 不关联宿主包。systemd PrivateTmp 的单独 mount namespace 只有在同 root、PID namespace、live unit 和文件视图一致时才可关联。

本地验收：Python 3.10，165 tests PASS；`bash -n scripts/ci_vm_smoke.sh` PASS；日志、JUnit、源码摘要同目录。CI 必须运行此源码的四格 VM 正向服务关联、无副作用 HTTP 标记响应和扫描前后状态检查，以及完整 fixture/Docker 矩阵。当前 CI NOT_RUN，不宣布阶段完成。

限制：VERIFIED_LOCAL_ASSOCIATION 是本地身份关联，不是厂商字节认证或补丁加载证明。静态 pools/routes 不是已加载配置或实际应用路由证明；动态 includes、站点覆盖、.htaccess、未知/自定义安装、CGI 等保留 UNKNOWN。配置关系不会解除自动规划门禁。没有任何实际修复执行能力。

首次 CI：Actions 39737441424 两格 Apache VM PASS；两格 FPM VM 在 HTTP 标记断言失败（FAIL），其余 fixture/container 检查见 ci-first-run.json 和 ci-first-failures.log。测试用 nginx 配置遗漏 worker user，默认 worker 无权连接 www-data FPM socket；修正测试配置为 `user www-data;`，不放宽扫描或关联断言。后续 CI 仍待验收。

最终验收：Actions [39738157981](https://github.com/ninex98/webpatch/actions/runs/39738157981)，源码 `c12855f35e942bbada8ef2f215a9bc3aabe79c3a`，9/9 jobs PASS。两版 Ubuntu 的 FPM/mod_php 主进程、包、systemd 服务关联断言与 HTTP 标记响应全部通过；普通用户与 root 扫描均不改变服务 PID 或系统配置/包状态。完整新日志、源码/制品摘要、JUnit、root/非 root 扫描在 accepted-ci/。上述本地关联与静态配置观察小阶段验收完成；应用级路由及已加载配置证明仍是明确未支持能力，不声称已安全。
