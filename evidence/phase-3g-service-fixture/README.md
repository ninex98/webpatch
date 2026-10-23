# 单 SAPI 测试隔离 / Single-SAPI fixture isolation

8e61800 的 Apache 正例正确阻断：fixture reinstall 同时启动了已安装的 FPM，而准备收据只声明 Apache。完整 census 没有遗漏 FPM。original-scope-failure.json 记录该事实和原制品哈希。

产品现在直接报告未准备消费者的 service/PID。测试只在采集证据前停止该 cell 未选择的另一标准 SAPI，并记录原状态；真实产品仍要求全部实际共享消费者被准备，绝不因此缩小扫描或忽略额外服务。旧版本 fixture 重置后也执行同一隔离准备。

本地 599 tests PASS，源码/JUnit/日志在本目录。四格实际生命周期重验 CI pending，开发宿主服务不变。
