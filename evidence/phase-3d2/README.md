# 3D.2 受控启动 / Controlled service startup

本地 PASS：454 tests；日志/JUnit/当前源码摘要见本目录。新增精确确认、计划说明篡改、不可信状态路径、代码 hooks/新模块、完整 pool 声明、只读 mount/inode 核对、签名收据及权限反例；unit/launcher/helper 身份单独验证。正向流程使用明确注入后端，不冒充真实服务测试。

CI 待验收 / CI pending：四格 VM 将在扫描/模拟不变检查完成后，下载实际所需的认证 archive、创建私有只读配置视图、确认后重启并验证每个声明 pool，检查收据防篡改，再清理自己的 runtime 定义并恢复测试服务。原额外 FPM pool 改为 static 维护测试配置，避免 ondemand 实例在长证据窗口中自然退出；产品对未稳定的 ondemand 配置明确阻断。

限制：此阶段不是包修复，apply 仍拒绝；动态/自定义配置、未知模块和缺失认证归档不获准准备。配置私有副本与签名密钥不上传/提交。真实 Linux service mutation 本地 NOT_RUN，只能在 GitHub-hosted VM 验收。
