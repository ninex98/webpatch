# 自定义安装范围 / Custom installation scope

99a652c 的 noble/fpm 中，签名启动、活跃消费者与全部 task 的 FD 覆盖均已通过；剩余消费者范围阻断来自 `/usr/local/bin/phpunit` 的未认证自定义安装线索。原制品摘要和精确阻断对象见 original-failure.json。

产品现在直接报告该路径，不凭文件名断言它一定只是安全 wrapper。临时 VM 在明确的 plain official-package fixture 中记录并搬移该工具，再采集证据；生产系统不执行此搬移。

本地隔离暂存源码 550 tests PASS，源码树/哈希、日志/JUnit 在本目录。执行衔接开发未混入这次提交。真实维护配置重验 CI pending。
