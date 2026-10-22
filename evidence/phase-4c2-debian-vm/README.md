# 4C.2 Debian 客体基础 / Independent Debian guests

本地 576 tests PASS，包括两个危险测试脚本在非 hosted 环境必须于任何 setup 前拒绝且不写目录；bash/compile 语法检查 PASS。本地 VM 启动、工具安装与服务操作 NOT_RUN。

CI pending：Debian 12/13 × FPM/Apache 的 QEMU 客体，源码由精确 Git commit 导出并校验，验证实际 systemd/文件身份；此阶段尚非 Debian 修复认证。无宿主文件系统共享，无 privileged 容器，无生产目标。

官方 cloud 镜像以 HTTPS+SHA512 核对内容，目录未提供镜像签名，不能宣称签名镜像认证。这个明确的测试环境来源边界保留于 guest-image.json；产品的 APT 认证不因此省略。SSH 私钥、客体磁盘与配置私有副本不上传。
