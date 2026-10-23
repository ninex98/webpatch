# 四阶段最终验收 / Final four-phase acceptance

**PASS：原设计四阶段在明确支持范围内完成。** 受测功能/测试/CI 源码：`941040c06cb29fc73cf64dcf81a78867d033f3e8`。Actions [39888070774](https://github.com/ninex98/webpatch/actions/runs/39888070774) **17/17 PASS**；取证时逐文件核对当前 src/tests/scripts/.github 与该源码一致。

| 独立验收 | 结果 |
|---|---|
| Python 3.10 / 3.12 | 各 617 tests，0 failures/errors/skipped，JUnit/coverage 日志保留 |
| Ubuntu 22.04 / 24.04、Debian 12 容器 | 3/3；原生包操作/锁/trigger/失败、只读禁网扫描/计划/重建建议、已安装包源码与文档字节核对 |
| Node Debian 12 / 13 | 2/2；独立 adapter/rules、真实包/改名进程和只读状态 |
| Debian 12 / 13 归档 | 2/2；独立官方签名根、Release/Packages/deb/文件链和损坏签名拒绝 |
| Ubuntu 22.04 / 24.04 × FPM/mod_php | 4/4；已安装公开 CLI 精确确认、真实同分支升级、新实例/视图/请求验证、错误 hash 和重复拒绝，以及显式真实健康故障 |
| Debian 12 / 13 × FPM/mod_php | 4/4 独立 QEMU 客体；同样的完整 CLI 成功与显式故障生命周期，独立环境/镜像证据 |

成功路径从 `/` 调用安装后的 `/usr/bin/webpatch apply`，不依赖源码目录/PYTHONPATH；结果为 `VERIFIED_WITHIN_DECLARED_SCOPE`、`safe=false`。每格故障路径经明确内部测试能力，在实际安装/重启后请求不可用 loopback 端口，返回 `PARTIAL`、`changed=true`；该故障能力不暴露给生产 CLI。

## 证据结构

- `run.json`：原始完成状态、17 个 job 结论、URL 和 source SHA。
- `validation.json`：全部受测源码 SHA256、下载制品摘要、选存路径和当前实施一致性。
- `artifacts/`：原始日志、JUnit、审计链、环境/镜像/源码清单、安装包摘要、错误/重复确认和部分小型模型。
- `lifecycle-results.json`：16 次最终事务的明确字段摘录，包含原文 SHA256、执行入口、版本/目标、精确 plan hash、复核和后验结论。
- `all-attempts.json`：所有尝试（含正确阻断的观察竞争）的字段摘录，不只保留最后成功。
- `documentation-check.log` / `documentation-validation.json`：最终文档的本地链接、当前 CLI help、源码差异/摘要核对。

大型重复 scan/plan/report、客体串口日志和二进制 `.deb` 不再复制到 Git，原 SHA256 全部保留；完整原文可从对应 Actions artifacts 获取。没有保存私钥、客体磁盘、venv 或缓存。最终文档/证据提交晚于受测源码；这些说明文字仅作本地文档校验，没有重建原生包或把旧二进制摘要说成新的。

## 失败与修正没有丢弃

- 旧模块夹具与复核诊断：`phase-3g4`；全内部基线：`phase-3g-accepted` 和 `phase-4c-accepted`。
- d314ead 两格 Apache 在安装前因短命进程/模拟输入竞争被正确阻断：`phase-3h-public`。CI 只对尚未变更的这些明确竞争生成新计划，最多三次，每次留证；生产没有自动重试，同一计划不能复用。
- ba5d9f6 八格已安装 CLI 已独立通过：`phase-3h-accepted`；Ubuntu 最小镜像文档过滤导致两格容器失败，原日志与修正：`phase-packaging-docs`。941040c 后完整矩阵通过。

## 限制 / Limitations

修复限定官方 amd64 Ubuntu 22.04/php8.1、24.04/php8.3、Debian 12/php8.2、13/php8.4 的标准 FPM/mod_php，同分支完整已安装 PHP source cohort；所有证据、明确请求、停机预算和精确确认仍必须满足。PPA/Sury/ESM、其他架构/分支、自编译/复杂配置、未知消费者、容器原地修复、CGI/FrankenPHP/LiteSpeed 不获执行支持。

Node 仅独立发现与两项已审阅 Debian 运行时规则，不是完整 CVE/npm 审计或 Node 修复。容器扩展只交付原设计的重建建议：镜像 digest 为声明，build/push/rollout **NOT_RUN**。规则有效至 **2026-10-29 00:00 UTC**，到期重新审阅来源。Debian 客体镜像的 HTTPS/SHA512 与 APT 签名链分别记录，镜像签名 **NOT_AVAILABLE**。

有限测试不认证任意站点、隐藏/未来任务或历史入侵；全部 safe=false，无自动回滚。开发宿主 PHP/APT/服务未修改，未执行生产修复或漏洞利用。公开签名 APT 仓库/正式 Release **NOT_RUN**，不属于本次四阶段交付。
