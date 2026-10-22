# Docker 运行期检查 / Docker runtime check

1db0afb 的三个 build 检查 FAIL 于隔离环境断言：BuildKit RUN 不提供 /.dockerenv，尚未执行任何测试包操作。保留 noble 原始日志。

改为从构建镜像运行独立、无网络、no-new-privileges 的临时容器；不使用 privileged、不挂载宿主 root/proc/socket。既有只读容器检查仍保留，写入测试仅位于另一个容器的可丢弃层。保留隔离断言，未删减门禁。

本地 478 tests PASS；实际 dpkg 生命周期仍 CI pending。
