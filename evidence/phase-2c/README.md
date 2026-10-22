# 阶段 2C / Real APT simulation — CI 待验收

范围：为 Ubuntu jammy/noble 认证的同分支精确候选执行真实 apt-get --simulate --no-download --no-remove --only-upgrade，独立临时 APT_CONFIG 禁用系统 hooks/缓存写入。来源、preferences、dpkg status、extended_states 来自当前系统；被省略的 hooks/特殊配置保留阻断项，不能据此执行实际修复。

完整解析 Inst/Conf/Remv 并交叉核对摘要计数、架构及 configure 集合；移除、降级、重装、新依赖、跨分支/发行版、候选漂移和未批准依赖改变均阻断。列出服务及 maintainer scripts 可能产生的中断，人工恢复需预先验证快照/备份，不承诺自动回滚。

计划 schema 2 使用冻结模型，绑定 boot/machine/namespace 作用域、规则、包、源、索引、缓存归档、配置和运行实例摘要；检查活动包管理锁、模拟前后状态、进程复用/新增及 30 分钟上限。verify-plan 只比较不可信 JSON 中的数据，重新扫描/模拟并检测摘要、过期、状态和求解漂移，绝不执行保存的命令。所有计划仍 BLOCKED/executable=false，apply 禁用。

本地 Python 3.10：242 tests PASS；bash syntax PASS；日志/JUnit/源码摘要同目录。CI 需要四格 VM 上真实模拟、保存计划再验证、真实系统状态不变，以及 real APT + synthetic older status 的目标/依赖更新解析。合成状态单独放临时目录，真实 dpkg status 与运行二进制不改变；不是旧漏洞环境或实际升级测试。当前 CI NOT_RUN，不宣布阶段完成。

限制：实际执行/服务重启/修复后应用健康验证 NOT_RUN 且不在本轮授权范围；未知身份、未知/动态应用路由、loaded configuration、第三方及镜像列表阻断；容器为重建建议；Debian APT 修复规划不支持。PASS 仅说明模拟命令和解析成功，绝不表示运行时安全或可以执行计划。
