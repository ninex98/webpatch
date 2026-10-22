# 2D.2 运行实例与路由证据 / Runtime and route evidence

最终限定范围 PASS：后续修正源码已通过两轮四格 VM；最终源码绑定见 ../phase-2d4/current-source-validation.json。以下保留原检查点、首次失败及修正过程。

本地 PASS：322 tests，日志/JUnit 和对应源码哈希见本目录；`bash -n scripts/ci_vm_smoke.sh`、`git diff --check` PASS。

实现标准 PHP 主映像/模块逐文件身份、FPM UNIX listener 归属、pool/静态 handler 的候选关联；命名空间、映射、socket 和配置变化可拒绝。加载配置和请求归属仍 UNKNOWN/NOT_CHECKED。新增测试覆盖认证字节正例、模块权限/删除/替换/未知包、监听 fd/namespace/状态变化、多个 pool/socket 和 Apache 条件配置。

CI 待验收 / CI pending：四格 Ubuntu VM 与三格 Docker 必须在推送后运行；此检查点不宣称 2D.2 真实环境已通过。VM 新增无害 mmap 删除/替换与配置修改反例，扫描不执行诊断请求。详细限制见 docs/phase-2d.md；实际修复 NOT_RUN_DISABLED。

首次 CI 实际 FAIL：Actions 39761142876 对 `0833be6` 的 fixtures（各 322 tests）和三组 Docker PASS；四格 VM 的 APT 模拟 PASS，但 verify-plan 保存文档读取失败。计划分别约 1.45 MiB（FPM）及 3.82 MiB（Apache），超过通用 1 MiB 上限。first-ci/ 保留失败完整制品与日志。第一次日志下载遇到 EOF，重试完成；收集脚本末尾因 run.conclusion=failure 正确返回非零。后续 `d5447b3` 加入独立 16 MiB 计划文档接口，等待完整重验。

最终有限范围验收 PASS：修正后的 Actions 39763556960 与最终 39763873264 均 9/9 PASS。后者四格包含多 pool/socket（FPM）、真实无害映射删除/替换、配置变化及状态不变；当前源码绑定见 ../phase-2d4/current-source-validation.json。只声明上述关系与失败语义通过，loaded configuration/request attribution 仍未证明。
