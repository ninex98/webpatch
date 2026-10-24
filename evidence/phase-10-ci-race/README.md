# 发布前 CI 进程观察竞争 / Release CI process observation race

2026-10-24 Asia/Shanghai。**本地策略测试 PASS；远端 VM 待验收。**

基线 run 39940345179（2af91b8）的 Debian 13 FPM 升级夹具在首次 repair review 因瞬时进程消失/描述符不可读/进程集合变化被正确阻断；原始 guest-test.log 留存在 baseline-fpm-failure.log。产品没有忽略这些证据缺口。

本次仅修改 tests：首次及事务前重新审阅均最多进行三次全量 scan + build_repair_review，间隔一秒，只有明确的进程集合变化/进程或描述符观察竞争允许重新取证，每次 document 均保存。其他阻断立即保持失败，不复用审阅摘要，不重试已变更事务，不放宽生产门禁。

验收：`pytest tests/test_ci_lifecycle_policy.py tests/test_ci_guards.py` 10 PASS；生命周期脚本编译与 diff 检查 PASS。实际 Ubuntu/Debian 升级/故障矩阵须等待新推送的 CI，本检查点不将旧 CI 作为通过证明。
