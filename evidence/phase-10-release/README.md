# 0.3.0 发布验收 / Release acceptance

2026-10-24（Asia/Shanghai）。**PASS：[v0.3.0](https://github.com/ninex98/webpatch/releases/tag/v0.3.0) 已公开发布并设为 latest。** 标签及附件源码为 `ec1c7783cb8428666de8249774a55629aacea2a0`。后续提交仅更新发布入口、文档和证据，不覆盖附件、不改写标签。

| 验收 / Gate | 结果 / Result |
|---|---|
| 完整安全 CI | **18/18 PASS**，[40056144430](https://github.com/ninex98/webpatch/actions/runs/40056144430)，同一 SHA，第二次 attempt 重新完成唯一失败格 |
| Python fixtures | Python 3.10 / 3.12 各 **698 PASS**，零失败/错误/跳过，JUnit/log 保留 |
| Docker 新功能 | 原生四容器及临时 Ubuntu 宿主上已安装 `/usr/bin/webpatch scan` **PASS**；包/自定义 PHP/无 PHP/停止容器逐项对应，状态与 filesystem diff 不变 |
| 真实修复回归 | Ubuntu 22.04/24.04、Debian 12/13 × FPM/Apache，**8 次已安装引导 CLI 升级 PASS**；另 **8 次故障注入保持 PARTIAL/changed=true** |
| 分发构建和四发行版安装 | **PASS**，[40056144427](https://github.com/ninex98/webpatch/actions/runs/40056144427)，每种 OS 23 场景 |
| 草稿发布及同源码安全门禁 | **6/6 PASS**，[40060237895](https://github.com/ninex98/webpatch/actions/runs/40060237895) |
| 草稿/受测附件一致性 | **PASS**，assets-validation.json，四附件集合和 SHA256 完全一致 |
| 公开 latest 下载新安装 | Ubuntu 22.04/24.04、Debian 12/13 arm64 新容器 **4/4 PASS**，非 root + sudo，初始无 Python，实际 HTTPS 下载/依赖安装/中文扫描 |
| 公开升级 | Ubuntu 24.04 非 root，**0.2.0 → 0.3.0 PASS**，新 Docker 参数可用，输出简洁 |
| 发布后代码一致性 | `git diff v0.3.0 -- src tests scripts .github pyproject.toml install.sh` 无差异；公开 tag 指向受测 ec1c778 |

安装包 SHA256：`a754f7da55a79fb49073d516353b25097296e5e9af8cd9712788ece00ef8bcd2`。`published-release.json` 记录公开状态及发布时间。四格安装结果均包含同一包摘要；草稿工作流重新构建的附件与初始分发完全一致。Git 中不包含生成的 .deb。

`safety/validation.json`、`distribution/validation.json`、`draft-ci/validation.json` 保存下载 artifact 的全部 SHA256、实际 job 状态、JUnit 计数与精简保留映射；完整下载留在被忽略的 ci-evidence，原始制品可在各 Actions run 获取。`lifecycle-validation.json` 逐项确认 8 次成功/8 次故障结果及调用入口。`online-validation.json` 根据每份完整日志末尾的 PASS JSON 核对结果，不能仅以 docker 退出码代替验证。

## 失败与后续验证 / Retained failures

发布前两个修正分别留在 `evidence/phase-10-ci-race` 和 `evidence/phase-10-docker-http`：测试夹具的瞬时进程竞争只允许完整重新取证，不放宽生产准入；Python 3.12 HTTPResponse 在响应完成后关闭 socket 的兼容性问题已修复，由真实 Unix HTTP、Linux Python 3.12 和已安装 CLI 的 Docker 验证覆盖。

受测提交 ec1c778 的安全 CI 首次 17/18 PASS，Ubuntu 22.04 Apache 在故障注入之前的准备阶段返回 PARTIAL / PREPARATION_APPLICATION_PROBE_FAILED。`first-safety` 保存原始失败日志、状态与证据摘要。没有复用该事务或降低断言；仅在全新 hosted VM 重跑失败 job，同一源码最终 18/18 通过。正常升级及独立故障注入都已通过，失败记录未删除。

第一轮公开安装 harness 通过 `bash -s` 流式提供脚本，部分 APT 子进程消费了后续脚本文本，安装成功但末尾断言未运行；这些日志保留于 `online-initial`，不作为完整通过证据。安装器调用改为 stdin=/dev/null 后，五个场景全部在新容器重新执行，并检查实际版本、JSON、Docker 参数、dpkg 不变性或升级输出。`online-harness` 保留最终脚本；所有测试容器已清理，没有宿主 root/proc/socket mounts 或 privileged。

## 发布范围 / Boundaries

默认 scan 自动检查一个可访问的本机 Docker daemon，支持自定义本机 socket；不自动遍历远端 Docker/Kubernetes/containerd。不执行容器内代码、不在容器内安装工具、不原地修复。Ubuntu/Debian 容器包复用已审阅规则；Alpine、自编译 PHP、头文件版本及未认证实际运行代码仍 UNKNOWN。所有 safe 字段为 false。

规则内容和期限未变，仍在 **2026-10-29 00:00 UTC** 到期。真实服务测试只证明声明的有限 profiles；不外推为任意生产网站安全保证。开发宿主 PHP/APT/系统包/服务未修改。README 的终端预览仍明确标记为历史 0.2.0 实际采集，当前版本徽标和安装入口已更新到 0.3.0。
