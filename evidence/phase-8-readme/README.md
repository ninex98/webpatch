# 阶段 8：安装优先的 README / Installation-first README

2026-10-23 (Asia/Shanghai). **PASS：中英文 README 已重排并精简。** 本阶段仅改 README、CLI 结果说明和证据，不改产品实现、版本或 Release 附件。

范围与验收：标题/短介绍之后首先展示安装与升级命令，紧接 CLI Preview，再提供八条常用命令。删除占据首屏的大横幅、重复的产品介绍、功能/安全/路线图长段落；完整结果解释移动到 CLI 文档，安装排错继续由安装文档承接。未知状态、修复确认、探针/归档条件、支持范围及规则期限保持明确。

英文 README 从 172 行缩为 73 行（字符量减少约 73%），中文从 180 行缩为 73 行（减少约 65%）。安装标题位于第 15 行、CLI Preview 第 27 行、命令表标题第 44 行；首个代码块就是可整体复制的单行安装命令。保留 quick-start、cli-preview、commands 锚点及移动端预览。

单行命令通过 && 串联创建私有临时目录、HTTPS 下载、安装和版本显示；完整下载失败时不执行脚本，临时目录自动清理。保留 retry-all-errors、超时和 HTTPS 重定向限制，未恢复 curl-to-shell 流式执行。

- `live-install.log`: 新的 Ubuntu 24.04 / arm64 disposable 容器，以普通用户执行本文档单行命令，真实下载、sudo/APT 安装后输出 0.2.0，PASS。
- `guard-results.json`: 复用前阶段隔离夹具，将新的单行命令作为 bootstrap 输入；curl 56 中断时返回 56 且无执行。已有单包下载/校验拒绝案例同时通过。完整结果及 stderr 保留，未修改夹具放宽要求。
- 文档结构、篇幅、锚点/本地链接、图片引用、shell 语法及 diff 校验通过；manifest.json 包含源码/文档/日志摘要、环境及本阶段结果。

执行命令：`docker run --rm -i webpatch-live-release:noble sh -s < evidence/phase-8-readme/install-one-line.sh`。拒绝路径在禁网隔离容器运行。没有 privileged 或宿主 root/proc/socket mounts，没有修改开发宿主 PHP/APT/服务。

整套产品 CI、用户服务器的网络、真实 GitHub 页面浏览器像素渲染 **NOT_RUN**；本阶段未更改产品代码，不把旧 CI 当作新的运行结果。当前实际校验覆盖文档结构与安装命令，不能保证任意用户的网络可达。
