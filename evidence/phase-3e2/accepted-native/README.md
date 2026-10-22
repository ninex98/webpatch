# 原生能力验收 / Native capability acceptance

Actions 39841958981，受测 commit 2ef6b0bcfefb1c582b98d73e0984f7f8ebc91193。Ubuntu 22.04、Ubuntu 24.04、Debian 12 三个独立 runtime 容器全部 PASS：合成包 1→2 真实升级、配置脚本与文件 trigger、前端锁冲突及故意退出 42 的 configure 失败；失败结果 changed=true，不冒充回滚。既有只读/禁网扫描检查也通过。

保存每格 build log、image identity、只读包内源码 hash 和 native-package.json，以及 run 元数据。validation.json 核对 9 个当前相关源码/测试文件与受测 commit 一致，并记录所有下载制品摘要。本目录没有 binary deb 或密钥。

本验收仅关闭 3E.2 的底层 capability 门槛。同一 run 的服务 VM 不全部成功，run 整体不能标为 PASS；3D.2 和真实 PHP 修复必须凭各自后续证据验收。合成包不是厂商来源认证样本，也不证明实际漏洞修复。
