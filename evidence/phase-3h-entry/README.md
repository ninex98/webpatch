# 3H 入口准备 / Public entry preparation

本地 605 tests PASS。新增禁用发布门禁零 I/O、缺少确认零 I/O、重复/嵌套重复 key、NaN/Infinity、注入能力缺失及显式能力下的类型化入口测试。成功 verifier 在该 fixture 中明确注入，不作为原生修复证明。

PUBLIC_REPAIR_ENABLED=false，公共 apply 仍拒绝任何实际操作。该状态只能由后续维护者源码提交在原生验收后切换，不能通过文档、环境变量或 CLI bypass。源码、日志/JUnit 在本目录，原生生命周期仍待最新矩阵。
