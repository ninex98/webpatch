# 3C 确认和事务状态机 / Confirmation and transaction state machine

本地 PASS：415 tests，日志/JUnit/当前源码摘要见本目录；source diff PASS。新增精确 hash、过期/门禁/范围未知、缺门禁、锁内漂移、安装部分失败、异常、重启/健康失败、日志失败和重复执行反例。注入后端正例验证完整调用顺序及锁范围。

CI 待验收 / CI pending：复用全矩阵回归。此阶段没有真实 OS 变更后端，apply 仍拒绝；正例是状态机 fixture，不能冒充四格 VM 实际修复结果。真实执行 NOT_RUN，完整修复准入仍 BLOCKED。
