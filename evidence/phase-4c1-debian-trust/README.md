# 4C.1 Debian 归档认证 / Debian archive authentication

本地 573 tests PASS，14 项独立 Debian cases 包括主钥/子钥、不同 key role、Codename/Label/Suite、有效期、篡改、混合发行版与固定 keyring 命令。Ubuntu 旧接口默认行为保留；Debian package repair 仍未获得准入。

来源及限制见 docs/phase-4.md。FTP keys 和 security FAQ 已读取；邮件链接读取 403，未当作已核验资料。两格真实 Debian 容器会用系统分发 keyring 验证实际签名、记录 keyring 版本/哈希，且要求已安装 FPM 文件匹配认证 deb，CI pending。

默认 scan 不下载、不导入 key、不更新索引、不运行服务。原始字段只用于其声明的身份关系，safe=false。当前源码/日志/JUnit 在本目录。
