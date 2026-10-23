# 阶段 7：命令速查与下载失败说明 / Command reference and download failure handling

2026-10-23 (Asia/Shanghai). **PASS：文档及安装指令验证通过。** 本阶段仅更改中英文 README、CLI/安装说明与证据，不改产品实现、已发布安装器、版本或 Release 附件。

用户反馈 curl 56 / TLS unexpected EOF 后 --lang 无法识别。公开 v0.2.0 仍存在；当前下载入口脚本 5600 bytes、SHA256 `5dde94933e06e5e9ba67f98cc8d4bc69a9eba15e227824c1e0cf0982547a9cb9` 与 Release 记录一致。实际本地下载先遇到 curl 35，启用 retry-all-errors 后 HTTP 200 成功（download-check.log/.err）。这验证了本次观察路径上的连接中断与重试成功，不能据此确定用户服务器的根因或保证其网络已恢复。

## 范围和验收 / Scope and validation

- README 靠前增加十行主要命令速查、用途/输出/修改系统边界和结果解释；修正 CLI 文档的旧版本、虚拟环境入口及 plan 必须带 --dry-run 的旧说明。
- 安装示例改为下载完整文件后执行，带有界重试和失败退出；不再将下载直接接给 sh。安装成功后打印 /usr/bin/webpatch --version；文档明确旧版不识别 --lang/fix、PATH 遮蔽的排查方法。
- 提供 v0.2.0 单包下载备用方式，保留证书检查、核对公开 SHA256 后才调用 APT；IPv4/HTTP 1.1 只是连接尝试，不冒充已经确诊的原因。
- `cli-help-validation.json`：所有列举命令/参数与 0.2.0 实际帮助一致，PASS；只运行 --help/--version，无宿主扫描或修复。
- `guard-results.json`：隔离、禁网容器模拟有效脚本下载中途返回 curl 56，两条配方均返回失败且不执行；损坏 deb 无法通过 SHA256，不调用 APT，3/3 PASS。第一版验证夹具存在字符串转义问题，失败日志在 initial-harness-failure.log；修正夹具后重跑，未改变待测配方来放宽要求。
- `bootstrap-live.log` 与 `direct-package-live.log`：普通用户、初始无 Python 的新 Ubuntu 24.04 arm64 容器，真实公开网络下载及 sudo/APT 安装，两条配方均 PASS，最后输出 0.2.0。
- Shell 语法、Markdown 本地链接/块结构、配方与文档字节一致性、diff 检查 PASS，摘要与环境见 validation.json。

容器命令：`docker run --rm -i webpatch-live-release:noble sh -s < <recipe>`。无 privileged、宿主 root/proc/socket mounts。产品规则期限及修复门禁不变；没有使用 -k、第三方代理或修改宿主 PHP/APT/服务。

入口脚本的重试不能修复持续不可达的网络，也没有改变已发布 v0.2.0 安装器内部下载的重试策略；后续下载仍失败时使用文档的已校验单包方式或可信电脑下载传输。用户服务器端重试结果 **NOT_RUN**。未重跑整套产品 CI；本次没有产品代码变化，先前源码验证不被改写成新的运行结果。
