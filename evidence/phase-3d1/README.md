# 3D.1 内核消费者清单 / Kernel consumer census

本地 PASS：427 tests，日志/JUnit/当前源码哈希见本目录；shell syntax、source diff PASS。新增独立于 comm 的文件身份发现、未登记消费者、权限/删除/替换/namespace/进程集合变化及无关匿名映射变化反例。

CI 待验收 / CI pending：四格 VM 新增真实 root procfs census 和改名 mmap holder 负例。只声明活跃映像/映射核对，未来/空闲消费者仍 NOT_PROVEN；不从空清单或 PID 名称推断安全。实际修复尚未启用。
