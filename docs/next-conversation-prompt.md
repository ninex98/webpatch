# 下一轮开发提示词

继续开发 WebPatch，工作目录 `/Users/ninex/Projects/hll-ecosystem/apps/webpatch`，仓库 `ninex98/webpatch`，优先使用已有 origin 和 Git 身份。先读取 AGENTS.md、docs/design.md、README.md、evidence/phase-2c/README.md 及各阶段 accepted-ci/run.json，核实当前 Git/远端/CI，不重新搭脚手架，不覆盖用户改动或远端历史。

## 当前实现与验收

- CI 基线已补齐：Ubuntu 22.04/24.04 × FPM/mod_php 的 amd64 GitHub 临时 VM，以及 Ubuntu 22.04/24.04、Debian 12 Docker。基线验收提交 d8d432f。
- 2A 本地运行实例关联已验收：starttime、namespace/root、文件映像、dpkg owner、systemd cgroup、FPM pools、mod_php 映射及静态 handlers。验收提交 9f74634，Actions 39738157981。
- 2B.1 软件源与包状态审计已验收：sources/deb822、Signed-By、第三方/混合源、pin/hold、hooks/特殊配置及异常包。验收提交 8be3bf8，Actions 39738531076。
- 2B.2 官方归档身份链已验收：固定 Ubuntu 签名指纹、InRelease、Packages 摘要、缓存 deb/control 与运行文件字节，真实篡改签名拒绝。验收提交 565f308，Actions 39743408335。mirror+file 未支持，保持 UNKNOWN；VM 正向测试在准备阶段明确配置 direct 官方源。
- 2C 已实现真实 APT simulate、完整依赖变化检查、冻结计划/过期/摘要、模拟前后状态核对和 verify-plan；所有计划仍 BLOCKED/executable=false。实现源码 37dc9d9，本地及 CI Python 3.10/3.12 各 243 tests PASS；Actions 39749809257 重跑后 9/9 jobs PASS，四格 VM 的真实模拟、保存计划核对、合成旧状态依赖求解与系统状态不变检查全部通过。Ubuntu 22.04/24.04 禁网只读容器升级求解也通过。最终验收证据见 evidence/phase-2c/accepted-ci/。

所有证据只证明其记录的源码。各阶段保留了失败日志和后续修正：FPM 测试 nginx worker 权限、runner mirror+file 来源未覆盖，整个 /proc 列表造成的扫描器 PID 假漂移、合成旧状态的同源依赖一致性，以及 no-download 对空缓存模拟的额外限制。不得使用旧成功结果覆盖新失败。完整源码/制品 SHA256、JUnit、VM 报告在对应证据目录；Git 未纳入二进制安装包。

## 未覆盖能力与下一步边界

先核实最新 CI，若有新失败则处理并留证；已验收源码之外的修改必须重新检查。随后推进用户本轮指定的下一阶段。不要自行启用实际修复执行。当前剩余边界包括：静态配置不是已加载配置证明；动态 includes、.htaccess、任意应用 HTTP 路由/健康、未覆盖 SAPI、自编译、第三方、镜像列表、ESM 和其他容器仍 UNKNOWN。Debian 仅官方版本对照，未认证归档修复路径。不能将这些未知折算为 SAFE 或自动执行资格。

2C 模拟使用独立临时 APT_CONFIG，保留系统 sources/preferences/status/extended_states，禁用 hooks 和系统缓存写入。被省略的特殊 APT 配置仍是阻断项。APT 模拟不持锁，不提供事务保证；真实升级、维护脚本重启、失败恢复和修复后健康验证属于后续显式授权的执行阶段。合成旧 dpkg status 的真实求解测试只改临时副本，没有安装旧漏洞二进制。

规则源于 PHP/Ubuntu/Debian 官方公告，审阅日 2026-10-22，有效至 2026-10-29 00:00 UTC。每次重新审阅须保存来源和摘要；禁止仅延长过期时间。不要把包版本、磁盘字节匹配、php -v 或安装成功当成运行时已安全。

## 工作要求与授权

1. 每个小阶段先说明范围和验收条件，实施后运行对应 checks，保留 PASS/FAIL/NOT_RUN/BLOCKED、JUnit/日志、环境与源码/制品摘要。
2. 验收后立即独立 Git 提交；标题和正文都包含中文与英文，说明验证和限制并报告 hash。云端必须先推送时可以创建明确标注 CI 待验收的检查点，全部必要门禁通过后才能宣布完成。
3. 继续允许自主配置项目本地工具/虚拟环境/Git/CI，允许正常推送到 origin 并运行 GitHub Actions；不强推、不覆盖已有远端历史、不发布 release。
4. 宿主 PHP、APT 源、系统包与服务不得修改。安装与服务测试只在隔离 Docker 或 GitHub 托管临时 VM 中，禁止 privileged、宿主 root/proc/socket 挂载和自托管 runner。开发依赖只在项目虚拟环境。
5. 默认只读，扫描不刷新 APT 缓存、不执行 PHP、不访问 Docker daemon 或应用站点。严格注入 fixtures 不回退宿主；使用普通标记响应而非真实漏洞利用。
6. 保持适配器、系统 I/O、模型、官方规则、身份链、规划、执行、验证的边界。未知环境保持可操作的 UNKNOWN 并阻断自动修复。实际运行修复仍需设计要求的审阅 dry-run 和显式确认，本授权不包含该操作。
