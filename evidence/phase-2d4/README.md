# 2D.4 已验收 / Current-source acceptance: PASS

源码 `efb122d9415ad2819c02fb958209b0e771d4715b` 的 [Actions 39763873264](https://github.com/ninex98/webpatch/actions/runs/39763873264) **9/9 PASS**：Python 3.10/3.12 各 336 tests、Ubuntu 22.04/24.04 与 Debian 12 三格 Docker、Ubuntu 22.04/24.04 × FPM/mod_php 四格 VM。完整日志、平台/镜像、源码及制品 SHA256、JUnit 在 accepted-ci/；二进制 deb 不提交，仅保留摘要。

`validate_evidence.py` 已核对 42 个当前源码/测试/CI 文件与 83 个保存制品哈希、JUnit 零失败/错误/跳过、三个容器结果和四格 VM 的计划/反例/进程不变结果，输出 current-source-validation.json。记录对应本次源码，不复用旧阶段通过数量。此前本地 336 tests、shell syntax 和 diff 检查 PASS，日志/JUnit/manifest 保留。

四格验证真实 systemd/PHP 模块关联、已认证文件、默认扫描没有运行 PHP 配置/发请求、真实 APT dry-run 和保存计划复核。FPM 有第二个 pool/socket；维护脚本/安装等价性和加载配置/请求归属门禁依然阻断。真实无害 mmap 删除/替换以及配置修改但不重启的反例均 PASS，配置被测试程序恢复。扫描/模拟前后相关 PHP/Apache PID/starttime、配置/APT/dpkg 内容保持不变；仅隔离 VM 的准备/故障注入执行写入。

历史：2D.1 39759702439 PASS；2D.2 39761142876 FAIL（计划读取上限），首次失败完整保留于 ../phase-2d2/first-ci；2D.3 39763556960 PASS（修正后）。本目录的初始本地检查点是在云端验收之前生成的，不能将其当独立 VM 结果。

限制 / Limitations：完整消费者清单、loaded configuration、request attribution、原生依赖/自定义模块覆盖、真实安装等价性、维护脚本/triggers/conffile 行为、停机审批、plan hash 确认、持锁执行和修复后健康/失败审计尚未闭合。`safe=false`、`executable=false`、`admission_status=BLOCKED`；实际修复 **NOT_RUN_DISABLED**。不认证任意生产拓扑，不包含真实漏洞利用或开发宿主系统改动。
