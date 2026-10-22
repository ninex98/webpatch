# 3A.2 显式应用证据 / Explicit application evidence

本地 PASS：380 tests；日志/JUnit/当前源码与平台摘要见本目录。`bash -n scripts/ci_vm_smoke.sh` 与 source diff 检查 PASS。严格 fake probe 不回退真实 HTTP；默认 scan 不调用探针。真实 Linux/PHP 调用仅在四格临时 VM 中验收。

CI 待验收 / CI pending：已扩展现有 VM 准备脚本，显式安装 root 控制 collector 并设 OPcache blacklist 后重启测试服务；这些仅是隔离环境准备。新 integration/application_check.py 验证内核凭据关联、真实普通标记没有回调的反例，以及 nonce/PID/响应篡改。检查点尚不宣称四格通过。

边界：VERIFIED_PROCESS_RESPONSE 不是完整请求覆盖或加载配置字节证明；effective PHP settings 只保存摘要，loaded_configuration_file_bytes 继续 UNKNOWN；不接收保存收据作为实时内核证据，不授权执行。实际修复 NOT_RUN_DISABLED。接口与官方参考见 docs/phase-3.md。

首轮 Actions 39770607606：8/9 PASS，三格 VM 完成真实探针。Ubuntu 22.04/Apache 在既有 runtime_check.py 无害 mmap helper 上失败：固定 90 秒存活结束后，慢扫描正确报告 PID/root 变化而非预期的删除映射原因。first-ci/ 保存真实失败 job 日志和完整 run 元数据。修正 helper 通过父进程 stdin 管道存活，finally 回收进程/管道；没有放宽扫描或反例断言。retry-local/ 380 tests PASS，云端重验待运行。
