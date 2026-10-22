# 3D.2 受控启动 / Controlled service startup

本地 PASS：454 tests；日志/JUnit/当前源码摘要见本目录。新增精确确认、计划说明篡改、不可信状态路径、代码 hooks/新模块、完整 pool 声明、只读 mount/inode 核对、签名收据及权限反例；unit/launcher/helper 身份单独验证。正向流程使用明确注入后端，不冒充真实服务测试。

CI 待验收 / CI pending：四格 VM 将在扫描/模拟不变检查完成后，下载实际所需的认证 archive、创建私有只读配置视图、确认后重启并验证每个声明 pool，检查收据防篡改，再清理自己的 runtime 定义并恢复测试服务。原额外 FPM pool 改为 static 维护测试配置，避免 ondemand 实例在长证据窗口中自然退出；产品对未稳定的 ondemand 配置明确阻断。

限制：此阶段不是包修复，apply 仍拒绝；动态/自定义配置、未知模块和缺失认证归档不获准准备。配置私有副本与签名密钥不上传/提交。真实 Linux service mutation 本地 NOT_RUN，只能在 GitHub-hosted VM 验收。

首轮 Actions 39832394765：fixtures/三格容器 PASS，四格 VM FAIL。Apache fixture 的旧预装版本已不在当前索引，无法认证下载；FPM fixture 的 systemd 空属性未输出，且 nginx 共享 include 被当作递归循环。first-ci/ 保存四个真实失败日志和 run 元数据。修正通过 systemctl --all 获取明确空值，使用递归 active stack 区分共享 include/真正循环（FPM 重复 include 继续阻断），并仅在 VM 基线准备时更新 Apache 到当前官方版本。没有放宽身份或未知门禁。retry-local/ 在暂存源码隔离目录验证 456 tests PASS，64 个源码/测试/CI 文件有对应哈希，待云端重验。
