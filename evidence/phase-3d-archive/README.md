# 归档解析身份绑定 / Sealed archive parsing identity

2026-10-23。本地 PASS：从 Git 暂存区导出的独立源码目录运行 434 tests，精确覆盖本检查点的 57 个源码/测试/CI 文件；manifest.json 保存逐文件 SHA256、暂存树标识、Python/平台与日志/JUnit 摘要。正在开发的受控启动文件未混入本检查点。initial-pytest.log 保留一次测试参数误用 pytest 保留名导致的收集失败，已修正。

修正使用预期签名摘要校验被复制的真实字节，再在 Linux memfd 上封存后交给 dpkg-deb 解析。缓存文件拒绝叶符号链接；返回元数据绑定封存摘要；路径前后校验仍保留，但不能替代该绑定。没有磁盘临时文件、服务变更或包安装。

CI 待验收 / CI pending：真实 Linux sealing/只读容器解析测试尚须推送后执行；macOS 本地未运行 Linux 内核接口。三个容器新增不可写、真实解析和错误摘要拒绝检查。只读服务定义查询和 Apache/nginx 索引记录也是后续受控启动身份核验的前置输入，不包含服务变更能力。
