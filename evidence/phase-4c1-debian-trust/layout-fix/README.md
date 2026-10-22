# Debian 实际布局修正 / Actual Debian layout correction

788f42f 两格原生认证 FAIL：bookworm-updates 的签名文件没有 Valid-Until；trixie sources 使用 .pgp keyring 路径。原始日志/run 元数据附后。

已读取官方 bookworm/trixie InRelease 头和 Debian 官方包文件清单 https://packages.debian.org/trixie/all/debian-archive-keyring/filelist 。仅允许该包明确分发的 .gpg/.pgp 两个固定文件名，仍要求相同固定主钥和角色。bookworm-updates 保持签名 Date 七天上限；security 和 trixie-updates 仍必须有 Valid-Until，缺失或过期拒绝。没有延长风险规则日期或容许任意 keyring。

本地 575 tests PASS，新增两个正反例；源码/JUnit/日志在本目录。真实认证链重验 CI pending，头字段观察本身不代替签名验证。
