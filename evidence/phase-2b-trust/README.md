# 阶段 2B.2 / Signed archive identity — CI 待验收

范围：只读验证已有 Ubuntu jammy/noble APT InRelease，固定 Ubuntu 2018 完整签名指纹；验证签名、suite/codename、时间、SHA256 表与解压 Packages 的长度/摘要。新鲜 security/updates 可提供规划候选；不可变 base pocket 只作身份比对，不作修复候选。无签名/过期/缺索引/多义版本保持 UNKNOWN。

`scan --package-cache /absolute/directory` 可读取事先获取的 .deb；完整 SHA256/长度匹配签名索引后，解析 control 和 tar（不执行、不解包至磁盘），比对包/源码/架构和 usr/bin、usr/sbin、usr/lib 下常规文件的 SHA256。缺少缓存包不从 dpkg 元数据臆造信任。AUTHENTICATED_RUNTIME_FILES 不等于证明历史安装来源、maintainer scripts、修改过的 conffiles 或运行进程安全。

本地 210 tests PASS；新测试覆盖签名错/未知 signer/过期、错发行版、索引和包损坏、control/架构/源码冲突、缓存缺失、运行文件替换及验证时变化。对应日志、JUnit、源码摘要同目录。真实 gpgv/apt-helper/dpkg-deb 验收需 CI 四格 VM，当前 NOT_RUN；VM 准备步骤下载目标包至临时独立缓存，扫描本身无网络/刷新。增加真实篡改签名副本的拒绝验证。

限制：Debian 保留官方版本规则但归档认证/修复规划未认证；第三方、ESM、自编译、未知配置/路由均阻断。签名根不证明已被 root 入侵主机的完整性；本轮没有执行修复。
