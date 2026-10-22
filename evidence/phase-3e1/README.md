# 3E.1 执行输入 / Execution input review

本地 PASS：468 tests；日志/JUnit/源码哈希见本目录。新增认证 metadata-only 包的严格正反例、显式组件 cohort，以及已安装脚本篡改/意外脚本/权限、特殊 dpkg 配置、现有服务 policy、pending trigger 和 registry 反例。所有新增审阅仍 executable=false。

CI 待验收 / CI pending：四格 VM 新增真实 dpkg admin 控制脚本匹配、dpkg 配置和 trigger registry 审计；负例只修改私有副本并经明确集成适配器读取，实际 dpkg info 文件不修改。命名 trigger 效果与执行审批仍需后续闭合，不能把此审计冒充包修复。
