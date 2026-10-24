# 0.3.0 发布准备 / Release preparation

2026-10-24 Asia/Shanghai。用户已授权推送并发布。程序唯一版本更新为 0.3.0，发行说明及 CLI/Docker 设计文档同步，规则内容与有效期未变。

本地全套 pytest **697 PASS**；版本读取、安装器 shell 语法及代码/文档 diff 检查 PASS。本提交为 **CI-pending checkpoint**：必须由同一 main SHA 的完整安全 CI、四发行版分发测试及草稿发布门禁通过后，才公开发布。此时远端 CI、公开安装升级均 **NOT_RUN**。

阶段 9 的 Docker 实现与前置测试竞争修正随本次推送；旧记录仅为历史证据，不代替当前代码的 CI 验证。
