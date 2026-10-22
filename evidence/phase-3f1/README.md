# 3F.1 收据复核 / Current startup verification

本地 489 tests PASS，包含精确收据摘要、签名篡改、过期、代码/规则与 scope/静态输入漂移、进程变更、可写 mount、effective 配置变化、recovery 收据混用和 fake I/O 无宿主回退。日志/JUnit/源码摘要见本目录。

真实四格 VM 复核 CI pending，依赖受控启动前置检查通过。verify-preparation 会显式重复声明的 loopback 请求，但不安装或重启；成功仅代表当前已准备范围，仍 executable=false。开发宿主未运行应用探针或服务变更。
