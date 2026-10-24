# WebPatch：架构、支持边界与实施计划

原始调研日期：2026-10-22（Asia/Shanghai）。Python ≥ 3.10，运行时仅标准库。

**阅读提示（2026-10-23）：** 第 1–7 节保留原始阶段设计和历史实现边界，不代表当前完成度。后续已实现受控准备、精确维护合同、事务/验证、Debian 归档认证/修复 profile、Node adapter/rules 和容器重建建议。原设计四阶段已按有限支持范围验收；当前原生证据及公开入口状态以 [development-status.md](development-status.md) 为准；操作说明见 [CLI](cli.md)。阶段四不承诺自动镜像发布或公开 APT 仓库。

## 1. 核实的事实与产品决策

PHP 官方确认两项漏洞影响处理 Web 请求的 PHP，包括 FPM、mod_php、CGI、FrankenPHP、LiteSpeed；mod_php 风险尤其高。上游修复版本为 8.2.35 / 8.3.36 / 8.4.27 / 8.5.12。8.1 及更早版本的发行版支持须单独判断。临时配置缓解不是完整修复，因此 WebPatch 不会据此给出安全结论，也不会自动修改内存限制。[PHP 公告][php]

两个 CVE 必须独立建模；本次公告中的修复边界相同，不代表未来规则必然相同：

| 厂商 / 系列 | 源码包 | 两项 CVE 的修复版本下界 | 依据 |
|---|---|---|---|
| Ubuntu 22.04 jammy | php8.1 | 8.1.2-1ubuntu2.28 | [USN-8948-1][usn]、[CVE 109618][u618]、[CVE 109619][u619] |
| Ubuntu 24.04 noble | php8.3 | 8.3.6-0ubuntu0.24.04.13 | 同上 |
| Debian 12 bookworm | php8.2 | 8.2.35-1~deb12u1 | [Debian 109618][d618]、[Debian 109619][d619]、[DLA-4848-1][dla] |
| Debian 13 trixie | php8.4 | 8.4.27-1~deb13u1 | [DSA-6574-1][dsa] |

决策：发行版包用发行版规则和 `dpkg --compare-versions`；禁止 SemVer、字符串比较或把上游版本下界套到 Ubuntu 回移植包。字段采用 dpkg 的 binary:Package、Version、Architecture、source:Package、source:Version 和 Status。[dpkg-query][query] / [dpkg][dpkg]

`apt-cache policy` 中的可用仓库不能证明已安装包的历史来源，同一个版本也可以来自多个源。APT 缓存可以过期，`apt-cache` 某些查询还会隐式生成缓存。APT 模拟不锁定系统，普通用户看不到全部配置时结果可能不完整。[APT cache][cache] / [APT preferences][prefs] / [APT simulation][apt]

因此阶段一甚至不调用 apt-cache；将“版本符合厂商修复边界”“包来源/字节可信”“正在运行的服务已加载补丁”“HTTP 路由实际使用此运行时”分开。包更新后服务可能还使用旧映像，Ubuntu 也明确要求相关服务重启。[Ubuntu 说明][ubuntu-blog]

## 2. 解耦架构

```text
CLI → ScanService → EnvironmentAdapter registry → SystemReader
                   ↓ Inventory + Evidence + CoverageGaps
              VendorRuleEngine ← 有版本/时效/出处的只读规则数据
                   ↓ PackageAssessment（不等于运行时安全）
              Planner → 不可变 Plan + Preconditions + Blockers
                   ↓ 明确授权边界（阶段三）
              Executor → Verifier → AuditJournal
```

- **SystemReader**：命令、文件、目录、符号链接接口；生产实现限定只读命令、固定环境、超时和输出上限。fixture 实现未声明的读取直接失败，不回退宿主机。禁止 shell、PHP 执行、读取进程环境及应用配置秘密。
- **EnvironmentAdapter**：报告能力，而不是用 OS 名称推定全部能力。APT 适配器只发现包；通用 PHP 适配器枚举常见安装位置、FPM/Apache/PHP 进程及命名空间线索。容器是独立扫描作用域，不跨 namespace 关联宿主机包。适配器不含 CVE 版本边界。
- **统一数据模型**：Environment、Package、RuntimeHint、Evidence、CoverageGap、PackageAssessment、Plan。源码包版本用于公告匹配，二进制包版本/架构用于安装与多架构身份。阶段一的 RuntimeHint 明确不是已验证的 runtime instance。
- **规则引擎**：纯数据规则按 `(vendor, release, source_package, CVE)` 寻址，通过注入比较器处理版本。规则带检查日期、有效期、来源和内容摘要。缺规则、过期、时间异常、未知版本族、查询失败均 UNKNOWN。禁止自动下载并运行远程规则代码。
- **Planner**：只产生结构化建议；阶段一全部计划 BLOCKED、空 actions，不把建议伪装成已执行 APT dry-run。后续规则仅给出修复约束，具体安装策略由 APT planner 决定。
- **Executor**：与只读 SystemReader 使用不同能力接口。阶段一没有可写实现；公开 `apply` 始终拒绝。后续也不接受任意 shell 命令或直接执行用户提供 JSON 中的 argv。
- **Verifier**：验证包、运行中的映像、服务与应用探针，不允许以安装退出码为修复成功。审计记录含计划摘要、状态转换、时间和证据，不保存凭据。

### 风险语义和普适性

阶段一只给出 `BELOW_VENDOR_FIX` / `MEETS_VENDOR_FIX` / `UNKNOWN` 的**包版本对照**；本地 dpkg 元数据可能来自重打包，前两者也不代表来源已认证。只有低于已知边界时总体为 `POTENTIALLY_AFFECTED`，其余为 `UNKNOWN`；始终 `runtime_status=UNKNOWN`、`safe=false`。没有 PHP 发现结果也不等于没有 PHP。

通用性来自稳定模型、证据接口和明确能力边界，而不是一个包管理命令覆盖所有服务器。未来 Node.js 复用发现/证据/计划框架，新增 runtime adapter 和 `RuleProvider` 实现；PHP 特定的 SAPI/源码包关联策略不直接套用到 Node，npm 依赖漏洞也与 Node 运行时漏洞分开。第三方适配器最初只允许随项目审核发布，暂不加载不可信 Python 插件。

### 阶段二/三必须实现的修复门禁

1. 在具体主机/容器作用域发现全部相关 SAPI、运行路径、服务单元、FPM pools 和 Web 路由；CLI 不代表 FPM。读取失败、混合版本、替换二进制、foreign namespace、未解析 include 均阻断自动修复。
2. 比对受信任 InRelease/Release 签名、Packages SHA256、包来源/版本/架构及运行文件身份。Maintainer、版本后缀或 Origin 文本均不作为单独信任根；本工具不承担已被 root 入侵机器的完整性证明。
3. 检查 sources.list 和 deb822 `.sources`、Signed-By、pin、hold、未配置包、dpkg 锁、ESM 权限、第三方源、APT hooks、conffile 提示及索引时间。刷新索引是写入操作，须经明确授权；可先在专用临时目录获取/验证索引，不改系统状态。
4. 锁定包的精确版本，完整模拟依赖解析；展示新增/移除/降级/跨发行版/源变更及服务中断。首版自动路径拒绝这些变化、PHP 主次版本迁移、不可信源和未批准的依赖变更。不能只检查目标包。
5. Plan 绑定规则摘要、作用域、包/配置/源/依赖摘要、过期时间、预计重启服务和人工恢复步骤。必须先成功 dry-run，再确认具体计划 hash；确认前后有变化或执行前重新模拟不一致则中止。
6. 包维护脚本可能自行重启服务，必须在确认前纳入停机预算。仅官方 Ubuntu 同分支更新可进入执行；不自动启用 PPA、不执行全系统 upgrade、不自动删除锁、不使用 force/untrusted 选项。
7. 执行后验证包、进程 starttime/inode 或映射身份、FPM/Apache 配置、服务状态和用户指定的无副作用健康请求。异常状态为 FAILED/PARTIAL/RESTART_REQUIRED，保留日志；APT 不具备事务回滚，不承诺自动降级恢复。修复也不等于排除历史入侵。

## 3. 首版支持矩阵

| 环境 | 阶段一（本次实现） | 首个可执行修复版（阶段三） |
|---|---|---|
| Ubuntu 22.04 官方 APT php8.1 FPM/mod_php | 包/进程线索、两项 CVE 版本对照 | 通过全部门禁后同分支更新和服务验证 |
| Ubuntu 24.04 官方 APT php8.3 FPM/mod_php | 同上 | 同上 |
| 上述系统多个 PHP / CLI 与 FPM 不一致 | 分包报告，不合并为系统版本 | 逐实例闭环；有未覆盖实例则阻断 |
| Debian 12/13 官方包 | 版本对照和只读发现 | 仅检测；不自动修复 |
| Ubuntu/Debian 容器内部 | 仅当前容器的包与进程线索 | 不原地修复；建议重建镜像、滚动替换 |
| 宿主机上的 Docker/containerd | 进程/命名空间/常见 socket 存在线索；不访问 daemon | 容器覆盖 UNKNOWN，不套用宿主包结论 |
| PPA/Sury、混合源、ESM、其他发行版系列 | 未知版本族或未知规则为 UNKNOWN | 不自动修复 |
| 宝塔 `/www/server/php`、自编译 `/usr/local`、`/opt/php` | 常见路径线索，补丁状态 UNKNOWN | 不自动修复 |
| CGI / FrankenPHP / LiteSpeed / CLI 内置服务器 | 包或进程线索（不保证穷举），UNKNOWN 运行时状态 | 不自动修复 |
| Windows/macOS、隐藏 PID、受限权限、无包管理器 | 可读证据及覆盖缺口，UNKNOWN | 不自动修复 |

“支持发现”不代表完整拓扑发现。阶段一不读取 FPM pool / nginx / Apache 路由配置，不证明监听端口或公网暴露，不核验二进制字节，不发现所有自定义目录，不遍历 Docker API；每份报告都带覆盖缺口。

## 4. 测试矩阵和可信度

| 层级 | 测试内容 | 能证明什么 / 不能证明什么 |
|---|---|---|
| pytest fixtures | ≥30 环境：jammy/noble/bookworm/trixie，新旧包、多 SAPI、多架构、PPA、epoch、tilde、binNMU、坏状态、空/错误元数据、过期规则、权限/超时、宝塔/源码、外部 namespace、删除中的进程 | 解析/保守决策/阻断边界；不能证明真实服务和仓库行为 |
| 独立反例 | 空清单、版本达标但进程旧、CLI 新 FPM 旧、文件被替换、来源伪造、假包名、无规则、读取失败都不能输出安全 | 防止危险的 false-safe；模拟结果不能代替签名验证 |
| 只读约束 | 严格 fake I/O 无回退；命令 allowlist；拒绝 apply；读取/输出限额；scan/plan 前后服务 PID、APT 状态和配置摘要不变 | 验证实际读取路径无主动写动作；不承诺 OS atime/audit 等元数据完全不变 |
| Docker | Ubuntu 22.04/24.04、Debian 12；真实 dpkg 比较/元数据、FPM/mod_php 包、构建 .deb、APT 本地安装、容器作用域、只读文件系统扫描 | Linux/发行版集成；无 systemd 的容器不能证明服务重启 |
| GitHub 临时 VM | ubuntu-22.04/24.04 × FPM/mod_php；APT 安装 .deb，启动服务，读取扫描，检查服务/配置未被扫描改变 | 真实 systemd 安装/服务冒烟；阶段三才验证修复生命周期 |
| 后续修复故障注入 | 源签名错/过期、依赖删除/降级、hold/锁、TOCTOU、网络/磁盘失败、维护脚本重启、健康检查失败、部分执行 | 门禁与失败状态；不以真实漏洞利用验证补丁 |

所有 fixture 不调用真实系统；所有安装和服务变更只在 Docker 或 GitHub 托管临时 VM 中运行。禁止自托管 runner 和把宿主 `/`、`/proc`、Docker socket 挂入测试容器，禁止 privileged。Docker 的真实 dpkg 测试用于校验 fixture 中预设比较结果，避免用自己写的比较器验证自己。

证据：每次阶段验收保存 pytest JUnit、命令日志、环境/镜像标识、源码摘要和结果说明。CI 上传制品。未运行、失败、跳过分别记录，不写成通过。冻结 fixture 测试可重复；真实 APT 冒烟依赖当时仓库，所以记录实际版本，不把它当历史漏洞环境。

## 5. 分阶段计划与验收门槛

| 阶段 | 交付 | 完成门槛 |
|---|---|---|
| 1：只读骨架（本次） | 本设计、审阅的离线规则、适配器/模型/注入 I/O、scan、阻断式 plan、.deb 构建、fixtures/Docker/VM 工作流 | fixtures 和本地 Docker 通过并留证；VM 工作流可审阅，未触发必须明确标记；无 SAFE/可写修复路径 |
| 2：可信发现与真实 dry-run | 完整 Ubuntu 服务关联、来源/文件身份、APT 仓库和依赖检查、不可变计划 | 异常矩阵通过；Ubuntu VM 上 dry-run 无变更；未知情况全部阻断 |
| 3：有限修复 | 显式确认、同分支升级、运行时/健康验证、失败审计 | 两版 Ubuntu × 两种 SAPI 的 VM 修复/失败路径通过；禁止借宿主测试 |
| 4：扩展 | 镜像重建建议、Debian 修复独立认证、Node.js 等新规则 | 每个适配器单独声明支持矩阵和验收证据 |

.deb 阶段一是本地 `apt install ./webpatch_*.deb`，无 maintainer scripts、daemon 或第三方 Python 依赖。公开 apt 仓库需后续建立签名、Release/Packages、密钥轮换和发布流程；当前不虚构可用仓库 URL。GitHub workflow 放在项目内，独立仓库发布后才会生效；当前父目录不是 Git 仓库。

[php]: https://www.php.net/archive/2026.php#2026-10-21-5
[usn]: https://ubuntu.com/security/notices/USN-8948-1
[u618]: https://ubuntu.com/security/CVE-2026-109618
[u619]: https://ubuntu.com/security/CVE-2026-109619
[d618]: https://security-tracker.debian.org/tracker/CVE-2026-109618
[d619]: https://security-tracker.debian.org/tracker/CVE-2026-109619
[dla]: https://security-tracker.debian.org/tracker/DLA-4848-1
[dsa]: https://security-tracker.debian.org/tracker/DSA-6574-1
[query]: https://manpages.debian.org/bookworm/dpkg/dpkg-query.1.en.html
[dpkg]: https://manpages.debian.org/bookworm/dpkg/dpkg.1.en.html
[apt]: https://manpages.debian.org/bookworm/apt/apt-get.8.en.html
[cache]: https://manpages.debian.org/bookworm/apt/apt-cache.8.en.html
[prefs]: https://manpages.debian.org/bookworm/apt/apt_preferences.5.en.html
[ubuntu-blog]: https://ubuntu.com/blog/php2shell-vulnerability-fixes-available

## 6. 阶段二实现补充（2026-10-22）

前文“阶段一”描述是基础版本边界。当前实现增加下列独立能力，验收记录分别见 evidence/phase-2a、phase-2b-sources、phase-2b-trust、phase-2c；以对应源码的实际 CI 证据判断完成状态。

- **运行实例**：稳定 starttime、mount/PID namespace、root identity、加载文件和磁盘 device/inode/SHA256、dpkg owner、systemd ControlGroup 与主进程关联。systemd PrivateTmp 通过相同 root/PID namespace/live unit/文件视图单独验证。FPM pools 和 Web handlers 仅为有边界的静态观察；动态 include、.htaccess、实际 loaded config/应用路由、未覆盖实例仍 UNKNOWN。
- **来源与身份**：严格解析 sources/deb822，审计 pin/hold、hooks、路径覆盖、dpkg 异常/diversions/pending updates。仅官方 direct Ubuntu jammy/noble 源启用固定 Ubuntu 2018 签名指纹验证；已有 InRelease → 解压 Packages SHA256/长度 → 缓存 deb SHA256/长度 → control 身份 → usr/bin、usr/sbin、usr/lib 常规运行文件的字节验证。扫描从不更新或下载。base pocket 仅用于身份比对，security/updates 要求 Date 不超过七天且未过 Valid-Until。文件认证不等于历史安装来源、maintainer scripts 或内存完整性证明。
- **APT 模拟**：通过独立 AptSimulator 能力，受限 argv 固定 simulate/no-remove/only-upgrade，干净环境和独立临时 APT_CONFIG；系统 sources/preferences/status/extended_states 被保留，hooks 不执行，特殊配置仍是阻断原因。simulate 本身不下载；不使用会在模拟时也要求现成缓存包的 no-download 选项，升级求解用禁网只读容器验证。解析并计数核对所有安装/配置/移除行；从未获得通用可写命令能力。
- **不可变计划**：冻结嵌套模型绑定当前作用域、规则、包/配置/源/索引/归档/进程摘要及最长 30 分钟有效期；先后检查快照与锁，保存摘要后可以 verify-plan 重新扫描和求解。APT 不持有系统锁，验证结果只是观察，不提供并发事务保证。未来执行器仍须再次核对全部门禁、显式确认计划 hash，并完成完整运行时/健康验证。

当前所有计划均 BLOCKED，apply 没有实现。密码学认证只覆盖上述 Ubuntu 归档；Debian、第三方、mirror+file、ESM 和自编译不是自动修复支持范围。临时 VM 安装服务与普通标记 HTTP 请求只验证测试环境，不将其扩张为任意生产站点的安全证明。

## 7. 阶段 2D 修复前证据契约（2026-10-22）

详细 schema、迁移和边界见 [phase-2d.md](phase-2d.md)。报告 schema 2 和计划 schema 4 增加实体化覆盖/作用域、共享包影响范围、PHP 映像及标准模块、FPM UNIX listener、静态 pool/handler 候选关联和统一门禁。扫描证据与模拟证据分开命名，逐门禁说明证据与解除要求。加载配置和请求归属仍不能从静态配置、监听 socket 或普通 HTTP 标记推导。

READY_FOR_REVIEW 仅说明有限诊断输入可审阅，执行准入仍 BLOCKED。计划有效期不超过扫描、规则、签名索引各自的边界；verify-plan 会重查实例/配置/依赖/门禁和时效。诊断模拟省略 hooks/部分特殊配置，维护脚本/conffile 和停机预算仍需阶段三审阅。当前 apply 始终拒绝，所有阶段三执行、验证与失败审计能力尚未实现。

2D.4 扩展原 CI，临时 VM 中比较相关进程 PID/starttime 和配置/APT/dpkg 状态，并注入无害映射删除/替换、配置变化等反例。当前验收进度和源码对应关系以 [development-status.md](development-status.md) 及 evidence/phase-2d4 为准，不能把有限测试站点扩展为任意生产环境保证。

## 8. 宿主机 Docker 只读发现（0.3.0）

`scan` 默认增加独立 DockerReader 能力；其他计划、准备和修复入口仍只使用原有当前系统证据。Docker 容器结果位于报告的 `docker` 字段，各自绑定容器 ID、镜像 ID、文件证据摘要和发行版元数据，不合并进宿主机 packages/assessments，不开放容器原地修复。存在低于已审阅厂商修复线的容器包时，scan 总体为 POTENTIALLY_AFFECTED / exit 1；其他情况仍 UNKNOWN / exit 2。

仅使用本机 Unix socket 的 GET/HEAD 固定接口：列出全部状态容器、读取进程名称、读取固定路径元数据及检查常见 PHP 路径。不给 DockerReader 写入或 exec 能力；不启动容器、不部署扫描器、不执行容器提供的 PHP/dpkg/shell、不读取 inspect 的 Env 或进程参数。不自动采用 DOCKER_HOST、Docker context、SSH/TCP 端点。常规 rootful/rootless socket 自动发现，也可显式指定本机绝对路径；默认选择一个 daemon，其他 daemon、远端编排器、隐藏/自定义路径明确未覆盖。

读取文件包括 os-release、dpkg status、Alpine APK 数据库和 PHP 安装头文件；固定常见路径使用 HEAD。归档仅在内存读取一个同名普通文件，拒绝符号/硬链接、目录、稀疏文件、重复条目及越界内容，不解包到磁盘。每个请求超时 3 秒、Docker 阶段总预算 45 秒、最多检查 64 个容器；JSON 上限 4 MiB，文件上限 8 MiB。前后重列清单能发现可观察的增删/状态变化，但不证明期间未重启或文件快照原子性，因此运行映像和路由始终 UNKNOWN。

Ubuntu/Debian 包继续复用原已审阅规则和宿主机受限 dpkg 比较器。读取到版本不认证来源、字节或实际运行进程。Alpine 和自编译 PHP 只显示安装/版本线索；不能把上游 informational-only 数据升级为已认证规则。缺失文件不证明 PHP 不存在，读取错误、超时、容器停止/消失逐个展示并阻断安全结论。规则文件、审阅时间、有效期均未改变。

API 依据：[Docker Engine API v1.45](https://docs.docker.com/reference/api/engine/version/v1.45/)、[container cp 与归档限制](https://docs.docker.com/reference/cli/docker/container/cp/)。此阶段的实际证据见 `evidence/phase-9-docker/README.md`；历史 CI 不作为新代码验收。
