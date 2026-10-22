# 修复后配置差异诊断 / Post-repair settings diagnosis

553657a 的真实升级已执行，但最终 PARTIAL：新包、新实例、只读视图、所有消费者及两个内核绑定请求通过，effective INI 摘要与升级前不同。original-partial.json 保存原制品摘要及事实；没有把它标为修复通过。

增加仅用于 disposable VM 的诊断页：PHP 在 www-data 私有 0700 目录保存随机盐的 HMAC，仅返回变化/新增/删除指令名称，不返回配置值、哈希或盐。该页不随 .deb 发布，不参与任何产品准入结论，生产 gate 不变。新 CI 预计仍会保持阻断并提供差异名，以便有依据地处理变化。

本地 573 tests PASS，日志/JUnit/源码摘要在本目录；真实配置差异尚待云端采集。此提交是诊断检查点，不是阶段三验收完成。
