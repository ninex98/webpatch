# 阶段 2B.2 / Signed archive identity — CI 待验收

范围：只读验证已有 Ubuntu jammy/noble APT InRelease，固定 Ubuntu 2018 完整签名指纹；验证签名、suite/codename、时间、SHA256 表与解压 Packages 的长度/摘要。新鲜 security/updates 可提供规划候选；不可变 base pocket 只作身份比对，不作修复候选。无签名/过期/缺索引/多义版本保持 UNKNOWN。

`scan --package-cache /absolute/directory` 可读取事先获取的 .deb；完整 SHA256/长度匹配签名索引后，解析 control 和 tar（不执行、不解包至磁盘），比对包/源码/架构和 usr/bin、usr/sbin、usr/lib 下常规文件的 SHA256。缺少缓存包不从 dpkg 元数据臆造信任。AUTHENTICATED_RUNTIME_FILES 不等于证明历史安装来源、maintainer scripts、修改过的 conffiles 或运行进程安全。

本地 210 tests PASS；新测试覆盖签名错/未知 signer/过期、错发行版、索引和包损坏、control/架构/源码冲突、缓存缺失、运行文件替换及验证时变化。对应日志、JUnit、源码摘要同目录。真实 gpgv/apt-helper/dpkg-deb 验收需 CI 四格 VM，当前 NOT_RUN；VM 准备步骤下载目标包至临时独立缓存，扫描本身无网络/刷新。增加真实篡改签名副本的拒绝验证。

限制：Debian 保留官方版本规则但归档认证/修复规划未认证；第三方、ESM、自编译、未知配置/路由均阻断。签名根不证明已被 root 入侵主机的完整性；本轮没有执行修复。

首次 CI：Actions 39739502752（d3a0d42）四格 VM 身份正向断言 FAIL；已保存 first-ci/ 全部日志、原始报告和制品摘要。报告显示 runner 使用 mirror+file/第三方源，当前策略正确拒绝该未覆盖来源，故无可认证候选。后续证据提交 8be3bf8 的同源码重跑 39739927084 同样失败，不计通过。

修正测试准备：仅 GitHub 临时 VM 中备份并摘要原始 sources，设置 direct Ubuntu archive/security 同发行版源，再更新测试索引。扫描器不自动改源，mirror+file 仍为 UNKNOWN，补充负向 fixture。隔离当前未提交的 2C 后，对该 2B 检查点复跑 211 tests PASS（retry-local.log/xml；retry-local-manifest/），shell syntax PASS。真实四格重跑仍待验收。

最终验收：Actions [39743408335](https://github.com/ninex98/webpatch/actions/runs/39743408335)，源码 `4effa761d9fdcb3bbd0c63e43b756b38383fd74d`，9/9 jobs PASS。两版 Ubuntu × FPM/mod_php 均真实验证 gpgv → InRelease → 解压 Packages → 缓存 deb → control → 已安装运行文件，且真实 gpgv 拒绝篡改后的签名副本。Python 3.10/3.12 各 211 tests、三组 Docker 与四格 VM 全部通过，扫描前后服务/配置/APT/dpkg 状态不变。完整日志、报告、JUnit 和源码/制品摘要见 accepted-ci/。2B.2 在上述明确范围内验收完成；未支持来源继续 UNKNOWN。
