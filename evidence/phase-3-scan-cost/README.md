# 共享归属观察 / Shared ownership observations

同一物理文件的 dpkg owner 是共享文件系统事实，不是每个 PID 的独立属性。单次 Collector 内只查询一次并复用同一 evidence ID；下一次 scan/持锁重新验证创建新 Collector，必须重新查询，不跨扫描复用。

新增双实例反例：首轮共享一个查询与证据；更改 owner 结果后下一轮确实重查，两个实例都变为 UNKNOWN。本地隔离暂存源码 549 tests PASS，源码树/哈希、JUnit/日志在本目录。未混入工作区正在开发的执行衔接代码。

真实矩阵 CI pending。此变化减少重复查询，不将安装来源或运行时安全从本地 owner 元数据推断为已验证。
