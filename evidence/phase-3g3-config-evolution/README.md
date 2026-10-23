# 3G.3 第二项已审阅新增 / Second reviewed addition

8e61800 的 jammy 原生差异：仅新增 max_multipart_body_parts，见 jammy-difference.json。核对 PHP 8.1.33 main.c 注册默认 -1 后，协议3只允许它和 memory_hard_limit_percent 各自从缺失到厂商默认；不是忽略全体新配置键。

本地隔离暂存源码 598 tests PASS；新增单项/组合新增和已存在值变化反例，保持其他未知阻断。源码树/JUnit/日志在本目录，未混入服务测试隔离修正。四格真实生命周期重验 CI pending，不修改任何资源限制。
