# 阶段三：有限修复前置接口 / Phase three prerequisite interfaces

## 3A.1 部署清单核对

`webpatch deployment-manifest --format json > deployment.json` 导出当前观察集合；`webpatch verify-deployment deployment.json --expect-sha256 <manifest_sha256>` 重新扫描并逐项核对。两者退出码为 4，不授予执行权限；参数/读取失败沿用 CLI 错误语义。默认 scan 行为不变。

清单 schema 1 绑定当前 scope、规则、输入摘要、包/运行实例/服务/pool/route/安装路径的独立实体与事实；有效期受扫描、规则和认证索引时效限制。missing、unexpected、changed 明确区分消失实体、新增实体与事实变化。重复 ID、额外字段、错误/重算摘要与固定审阅 hash 不一致、过期、范围或规则变化均拒绝；重算摘要不能掩盖从清单删除仍在扫描结果中的消费者。

`MATCHED_OBSERVATIONS` 仅说明清单与当前观察集合一致。导出文件不是独立部署发现来源，不能证明穷举；completeness 固定 UNPROVEN，authorization 固定 NONE，空清单也不构成完整覆盖。调用者自行写 COMPLETE/approved 字段不会解除门禁。这是后续显式应用证据、操作者审阅和有限执行输入的一项核对接口，不替代实际证明。

后续 3A.2 将实现独立的显式应用证据能力，在受限 VM 中验证 challenge、来源、进程与配置/请求归属；默认 scan 不执行该能力。

## 3A.2 显式应用证据

`webpatch probe-template` 仅输出随包附带的 PHP collector，不扫描、不部署。操作者需另行部署该文件于 root 控制且不可被应用用户改写的路径，PHP sockets 扩展必须可用，collector 不可在 OPcache 中缓存。`webpatch probe-application --url http://127.0.0.1:18080/webpatch-proof.php --script /var/www/html/webpatch-proof.php --service php8.1-fpm.service --format json` 才显式发起一次 GET 请求。默认 scan/plan 不调用这个能力；不支持远程 URL、重定向、查询参数或自动部署。macOS/非 Linux 没有该内核凭据能力。

探针生成一次性随机 challenge，HTTP 返回值必须与同一 challenge 的 UNIX datagram payload 摘要匹配。Linux SCM_CREDENTIALS 提供发送 PID/UID/GID，不能以 JSON 自称 PID 替代；将该 PID 关联已扫描且稳定的 starttime、namespace、映像/模块、systemd 服务和 SAPI，并在请求前后复查输入。内核 abstract UNIX namespace 支持 systemd PrivateTmp；不创建目标配置文件或文件系统 socket。HTTP 与 datagram 有长度/时间上限。PHP 8.1 的 socket_sendto 不支持此处需要的 abstract 地址，实际使用支持二进制地址长度的 socket_connect + socket_send。

结果 `VERIFIED_PROCESS_RESPONSE` 只证明该一次性响应和回调发送进程的对应关系；应用用户/受损应用代码的行为并未被远程证明。root 控制的磁盘脚本来源也不是进程内存/正在执行 opcode 的完整性证明。该结果不等于任意生产请求路由覆盖，不直接解除现有 loaded_configuration 或完整消费者门禁。当前 API 不接受保存的 receipt 冒充新的内核观察。

配置结果为 `OBSERVED_EFFECTIVE_PHP_SETTINGS`：仅保存 ini 文件路径、effective ini/扩展列表的摘要，不保存配置值或秘密。`ini_get_all` 不含部分数组配置；磁盘配置可能在启动后变化。因此 `loaded_configuration_file_bytes=UNKNOWN`，`executable=false`；有效期最多五分钟且受扫描/规则/索引边界限制。真实准备和调用在四格 disposable VM 中单独进行，实际 PHP 执行不发生在开发宿主。

参考（2026-10-22 审阅）：[Linux UNIX credentials](https://man7.org/linux/man-pages/man7/unix.7.html)、[Python recvmsg](https://docs.python.org/3/library/socket.html#socket.socket.recvmsg)、[PHP ini_get_all](https://www.php.net/manual/en/function.ini-get-all.php)、[PHP loaded INI](https://www.php.net/manual/en/function.php-ini-loaded-file.php)、[PHP 8.1 sockets 实现](https://github.com/php/php-src/blob/PHP-8.1/ext/sockets/sockets.c)。这些资料支持具体 API 语义，不构成运行时安全证明。

## 3B 精确候选维护行为审阅

`webpatch review-maintenance --dry-run --target-package php8.1-fpm:amd64 --package-cache /path/to/authenticated-cache --format json` 先重新扫描并生成诊断计划，再检查精确目标及依赖变化所涉及的新旧归档。输出绑定 plan hash、scope 和有效期，附带可审阅的维护脚本文本/摘要、triggers、conffile 列表与本地冲突；不会执行脚本。只保存认证包中的公开脚本文本，本地配置只保存摘要。

每个新旧归档必须匹配受信任索引的名称/架构/版本/源码身份和 SHA256/长度，并在读取后复查未替换。控制归档拒绝路径穿越、重复、非普通控制文件和超限；不透明脚本、缺失归档、无法核对的 conffile payload、remove-on-upgrade 及本地配置变化保持阻断。新旧版本合并显示角色，防止只审阅新 postinst 而遗漏升级时可能使用的旧脚本。

`READY_FOR_MAINTENANCE_REVIEW` 只说明可开始具体内容审阅，不证明维护脚本无副作用，也不证明全系统 trigger cascade。磁盘 dpkg 管理脚本的独立身份、ucf 等脚本管理配置、真实安装行为和停机预算仍须后续门禁；不会因列表为空或脚本退出码可预测就直接授予执行权限。

参考（2026-10-22 审阅）：[Debian maintainer script lifecycle](https://www.debian.org/doc/debian-policy/ch-maintainerscripts.html)、[conffile 格式及 remove-on-upgrade](https://manpages.debian.org/bookworm/dpkg-dev/deb-conffiles.5.en.html)。

## 3C 确认、事务状态机与审计接口

transaction.py 定义独立 TransactionBackend：locked、revalidate、install、restart、verify；本小阶段没有真实 OS 变更后端，也没有将其接入 apply。执行入口只接受当前代码生成的类型化 Plan，不派发保存 JSON 中的 actions/argv。

状态机先检查完整必需门禁、逐项覆盖、受影响范围完整性、模拟成功、计划摘要/时效和显式确认的完全相同 hash，再进入锁内重新验证。缺任何必需门禁、UNKNOWN/NOT_RUN/未解决 blocker、未核实影响范围或动作字符串均阻断。当前真实 planner 仍输出 BLOCKED，因此不会触发后端。

成功路径为 PRECHECK → INSTALLING → RESTARTING → VERIFYING → VERIFIED_WITHIN_DECLARED_SCOPE，结果不叫全局 SAFE。失败区分安装前 FAILED、可能已变更的 PARTIAL、RESTART_REQUIRED 和验证失败；不重试安装、不执行自动回滚。同一计划一旦留下尝试记录，重跑需要生成并审阅新计划。安装/重启抛异常时保守认为可能变更，异常正文不进入日志。

AuditJournal 使用 0600 普通文件、有界 JSONL、追加写入/fsync 和 hash chain，拒绝坏链、开放权限或非本用户文件。它依赖外层事务锁，不声称 hash chain 本身提供并发互斥或 root 级完整性证明。安装前日志写入失败会阻止安装；无法写入失败记录时在结果中明确标记。锁失败时不写入其他事务的日志。

测试中的可执行正例仅由注入后端和明确构造的已满足门禁 fixture 提供，用来验证事务顺序及失败边界，不是生产准入证据。真实有限执行、受控配置加载与完整消费者核验仍须后续独立验收。

## 3D.1 活跃映像/映射消费者核对

`webpatch audit-consumers --target-package php8.1-fpm:amd64 --package-cache /path/to/cache --format json` 按认证归档文件的 device/inode/SHA256 建立目标索引，读取全部可见 PID 的 stat、exe identity 和 maps，与已有运行实例/服务逐项关联。它独立于 comm 名称，能发现改名、未列入初始运行清单的映射持有者和删除/替换映像。读取失败、进程新增/退出/身份变化、映射异常、作用域变化与未知包文件身份均阻断。

`VERIFIED_ACTIVE_MAPPING_CENSUS` 只证明该时间窗口内的活跃文件消费者被核对，不证明未来任务、空闲服务或不可见的部署范围；idle_and_future_consumers 固定 NOT_PROVEN，executable=false。内核线程或 zombie 的空地址空间与一般读取失败分开；只比较目标文件映射，普通匿名 heap 变化不触发无关漂移。空进程集/无消费者仍不能证明完整覆盖。

四格 VM 以真实 root procfs 做正例，并启动只 mmap 认证包文件的无害 Python helper（comm 不含 PHP）作为额外消费者反例。允许最多三次读取快照以处理正常 PID churn，保存每次结果，不跳过失败项或放宽门禁；不会执行映射的 PHP 二进制。

## 归档解析绑定修正（2026-10-23）

受控启动前补强已认证归档的解析链：调用方必须提供签名索引中的预期 SHA256，读取时将归档字节复制到 Linux memfd 并在摘要相符后施加 WRITE/SHRINK/GROW/SEAL 限制；dpkg-deb 的两次 tar 读取都使用继承的同一封存文件描述符。没有磁盘临时文件或目标系统写入。缓存归档指纹拒绝符号链接，解析输出也保留实际封存字节的摘要，不能用路径读取前后碰巧一致的元数据替代实际解析内容的身份。

普通只读命令接口不接受 `/proc/self/fd/*` 解析命令；只允许内部持有封存 FD 的解析能力传递它。Linux 能力不可用时返回明确 UNKNOWN/未支持原因，不回退到未封存路径。三个只读、禁网容器验证真实 memfd 不可写、真实 dpkg-deb 能读取封存数据、错误摘要在解析前被拒绝。[内核接口说明](https://man7.org/linux/man-pages/man2/memfd_create.2.html)

同一检查点增加只读 service definition 查询及 Apache/nginx 索引身份记录，作为后续受控启动核验的输入；这些接口不能执行服务变更。

## 3D.2 受控启动与只读配置视图（CI 待验收）

prepare-plan 只读取证据，列出精确服务、每个 FPM pool 的显式 collector 请求、配置文件摘要、认证服务定义、预计中断及本地状态目录。prepare-scope 必须确认完全相同的 preparation_sha256，并在独占操作锁/DPKG frontend lock 内重新扫描核对；过期、代码变化、额外字段、伪造动作说明、遗漏 pool 或不受支持的输入均拒绝。当前仅支持标准 Ubuntu jammy/php8.1、noble/php8.3 FPM/mod_php 服务，不支持容器原地准备或自定义 unit/drop-in/environment files。

身份前置条件覆盖认证归档中的 unit、主程序、实际映射的 PHP 模块以及服务/辅助包的运行文件；Apache 的 envvars 必须与认证包相符。读取的控制/数据归档使用封存字节。服务定义的公开源文本可以进入计划；配置值不会进入计划/收据。

经确认后，控制器在 0700 状态目录复制计划中的服务器配置内容（私有快照确实包含配置值，应按配置备份保护），生成认证 vendor unit 的临时 runtime 定义并加入 BindReadOnlyPaths。它在 daemon-reload 后核对实际载入的定义，再重启声明服务。正式 /etc 配置文件没有被编辑，包没有被安装。代码 hooks、新/未知扩展、动态加载、非标准 user_ini 文件名以及 ondemand 不稳定维护配置先行阻断。临时 unit 原子写入；已有 runtime unit 不覆盖。

重启后核对新 PID/starttime、内核回调、每个声明 pool、实际 mountinfo 的只读标记，以及 /proc/PID/root 下每个配置文件与私有快照的 device/inode/SHA256。配置被固定在该进程的只读 namespace 视图中，因此不以 mtime 或“重启退出码 0”替代加载输入证明。仅声明已冻结的配置输入和明确 probe 请求中的 PHP 视图；不证明任意生产拓扑或业务逻辑。

验证通过后由本机 0600 随机密钥认证 controlled_startup receipt，绑定 scope、代码/静态输入、实例和证据期限；非 root 调用者无法仅修改 JSON 后重算普通摘要来伪造该记录。它不是 root 妥协证明。独立探针仍默认五分钟，已验证只读配置视图的受控启动证据最多三十分钟，且不得超过计划、规则或索引期限。apply 的包执行仍禁用，收据本身不等于修复授权。

retire-preparation 需要同一主机密钥、相同 scope 和精确收据摘要，只移除收据拥有且内容未变的 runtime 定义并重新加载 manager。它不重启服务，当前只读视图一直保留到进程退出；未来启动使用正式配置。失败准备返回 PARTIAL 及可用的签名 ownership/recovery receipt，并记录阶段；不承诺自动恢复服务。四格 VM 会在原有只读不变检查之后单独执行准备/清理，恢复标准 unit 并重新启动测试服务；开发宿主不会运行控制器。

## 3E.1 执行输入审计与同源组件

`plan/review-maintenance/review-execution --source-cohort php8.1 --dry-run` 可显式选择同一 PHP 源码分支的全部已安装包，包括同源组件；与 --target-package 互斥。默认仍只规划 engine 包。计划 schema 4 新增 target_policy，省略时按 ENGINE_PACKAGES 解读，组件计划使用 EXPLICIT_SOURCE_COMPONENTS 并在 verify-plan 中保留；仍然阻断包执行。

完整、认证且没有控制脚本/trigger、payload 仅含文档/元数据的包可以标为 AUTHENTICATED_METADATA_ONLY_ARCHIVE；这仅是归档内容分类，不是空发现证明或运行时安全。任意 runtime 路径、越界 symlink、空 payload 或控制脚本都不能获得该分类，engine 空 payload 仍 UNKNOWN。

review-execution 同时核对磁盘 /var/lib/dpkg/info 下旧维护脚本/trigger 与认证旧归档的字节、所有者和权限；归档中缺少脚本时，磁盘上也必须明确缺少。dpkg 特殊配置、已有 policy-rc.d、未完成 trigger 活动和不可读 registry 保持阻断。文件 trigger 候选按完整 payload 路径列出，多个 handler 均保留；维护脚本的命名 trigger 激活仍需要显式审阅。READY_FOR_EXECUTION_POLICY_REVIEW 不是执行准入。

这些输入为受限执行器提供事实；未来不能直接把 APT 模拟与安装等价。实际执行策略须在确认计划中明确维护脚本、trigger 处理、服务启动策略、锁与异常状态。

## 3E.2 有界包操作能力（CI 待验收）

package_control.py 是独立、尚未接入 apply 的可写能力。策略层必须先提供精确类型化归档与已审阅 trigger 集合；本模块不把调用者 JSON 当审批，不解析其 argv。归档先经过封存解析身份核对，再复制进 root 私有事务目录并重新哈希；只从该目录运行固定 dpkg unpack/configure/triggers-only 步骤，无网络、移除、降级选项或 force 选项。已存在事务目录不能重复使用。

父进程实际持有 dpkg frontend POSIX lock，子 dpkg 使用文档规定的 DPKG_FRONTEND_LOCKED=true 并继续持有自己的 backend lock。不能用 APT 的模拟成功冒充该执行策略等价；APT 不支持把外部持有的 frontend lock 直接当自己持锁，因此此能力不运行 apt-get install。后续精确确认计划必须显示这一区别，并重新核对所有依赖和脚本输入。

临时 policy-rc.d 以完整固定字节原子发布，必须原本不存在；退出 101 抑制遵循该接口的维护脚本服务启动。它不能证明任意脚本不会直接调用 systemctl，所以脚本行为仍由准入策略审阅。清理仅删除本次拥有且未改变的文件。维护输出保存为私有 0600 有界日志，返回摘要；超时或输出超限终止进程组并报告可能已变更，不自动重试/回滚。仅批准的 pending trigger 可运行，级联轮次有上限，未知 handler 留在 PARTIAL 供人工恢复。

即使精确版本全部配置完成，结果仍明确 RUNTIME_VERIFICATION_REQUIRED。三个 disposable build 容器用无害合成包验证真实 1→2 升级、维护脚本和文件 trigger 顺序、真实 frontend 锁冲突及 configure 失败后的 changed 状态。这些归档不代表发行版认证或真实 PHP 修复；它们只验收底层执行能力。

参考：2026-10-23 审阅 [dpkg 环境及 trigger 行为](https://manpages.debian.org/bookworm/dpkg/dpkg.1.en.html) 与 [APT 锁实现](https://github.com/Debian/apt/blob/main/apt-pkg/deb/debsystem.cc)。

## 3F.1 受控启动收据的当前复核

`verify-preparation startup-receipt.json --expect-sha256 <整个签名收据的摘要> --state-directory /var/lib/webpatch --package-cache <缓存>` 重新扫描并显式重复收据中的 loopback collector 请求。它不重启、不安装；成功退出 0 仅表示 VERIFIED_CURRENT_PREPARED_SCOPE，executable 仍为 false。

签名收据新增实施代码与规则摘要。复核要求同 scope、有效时间、同静态输入、完全相同的稳定实例集合、当前载入的受控 unit、真实只读 mount 与文件 inode/hash，再取得新的内核绑定请求和同 pool/effective 配置摘要。旧格式缺少来源字段、过期、代码/规则变化、进程替换、配置视图可写或请求失配均阻断；ownership/recovery 收据不能充当成功启动收据。保存的 JSON 自称完整不能替代这些独立观察。

四格 VM 将在成功准备后立即复核真实收据及新请求；这仍是准入前证据，不是包修复完成。

## 3F.2 统一受控修复审阅（CI 待验收）

`repair-plan --prepared-receipt startup.json --source-cohort php8.1 --budget-seconds 600 --refresh-probes --state-directory /var/lib/webpatch --package-cache <缓存>` 显式重新发起已声明探针、执行 APT 模拟并整合证据；不安装或重启，退出 4。它生成 managed_package_repair_review，内含 schema 5 Plan 和由 plan hash 绑定的 execution_contract_sha256。原诊断 plan 仍 schema 4；旧计划不会被当作受控修复计划。

初始维护配置限定 Ubuntu jammy/noble amd64、同一 PHP 源码分支全部已安装成员、已认证配置快照和稳定服务。认证元数据包与 engine 区分；不再把“非 engine 无 CVE 对照”的组件结果当已选 engine 的规则失败，但所有组件候选、归档和实际字节仍独立核对。未知选定 engine、源、签名、模拟、依赖、锁或输入漂移均阻断。

计划完整列出旧/新维护脚本、conffile、实际 dpkg 管理脚本和触发器。文件 trigger 候选及所选源码组的已声明 handlers 必须有认证旧归档，磁盘脚本与相关执行文件匹配；仅这些 pending handlers 可进入后续受限操作能力。预依赖只支持已配置且不参与此次变更的简单依赖及 >= 约束，复杂表达式或变更中的预依赖阻断。目标 payload 的 diversion/statoverride 阻断；无交集的条目保留精确路径和依据，不删除记录。

完整扫描及所有全局 UNKNOWN 保留在 evidence，操作范围只声明精确包文件和当前已核对的共享消费者。当前 active mapping census、签名启动、只读配置视图与每个已声明请求必须通过；不将此结论扩张成任意未来任务、其他镜像或全站路由安全。仍需后续执行器阶段完成所有实际运行/失败闭环后才能接入公共 apply。本小阶段的 READY_FOR_CONFIRMATION 是待确认的类型化审阅结果，executable=false；无包变化为 NO_PACKAGE_CHANGES 且执行准入 BLOCKED，不伪造一次修复。

四格 VM 在原有只读不变检查之后，单独建立明确的 plain APT 维护配置，保存被搬移配置摘要，并准备实际需要的官方 cohort/handler 归档。产品不自动清理 APT 配置。此正例验证当前修复版的 NO_PACKAGE_CHANGES；后续必须独立证明旧版到修复版的真实升级。已有 jammy/Apache job 在 20 分钟处取消，新增核对后 VM 超时预算调至 35 分钟；产品命令时限未放宽。

## 3F.3 文件描述符、完整代码绑定与时间窗口

消费者 census 现在读取每个可见 PID 的全部 task 文件描述符表，包含线程 unshare(CLONE_FILES) 后的独立表。普通文件按 device/inode 与目标归档文件关联，改名/硬链接别名或仅 open 而未 mmap 的持有者同样计入影响范围。读取失败、线程身份/集合变化、目标描述符变化和目标磁盘字节在 census 内改变均阻断。枚举有线程、条目和字节上限；每个 PID 保留有界结构摘要与证据哈希，不把无关已打开文件路径加入公开报告。file_descriptor_coverage 缺失或 UNKNOWN 不能准入。

启动收据和修复合同改为绑定全部随包 Python/PHP/JSON 实施与规则资源，避免手工文件列表遗漏消费者或其他模块。旧收据需重新准备。注入 reader（包括 LocalSystem 子类）须显式注入探针、模拟、控制器和审计能力，不会自动回退宿主能力；缺少 reader 能力记录 CAPABILITY_UNAVAILABLE 并保持 UNKNOWN。

探针/收据/census/整体审阅在完成时复查实际时间，真实调用不再因为传入起始时间而冻结时钟。事务在持锁重新验证返回后再次检查计划时效，过期则 ABORTED，不进入安装。测试时可显式注入固定时钟；该测试能力不从保存 JSON 获取。

原生验收新增普通文件 FD 读取、仅打开未映射文件的进程、独立线程文件表三类无害案例；无漏洞利用。此能力证明当前可见文件持有者，不证明未来任务、复制到匿名内存的代码或历史入侵不存在；结果仍有有限 scope 和全局 UNKNOWN。

## 3G.1 受控事务衔接与真实生命周期（CI 待验收）

repair_execution.py 接收 schema 5 审阅文档，严格解码固定模型，核对完全相同的确认 hash、合同和原始审阅证据摘要；未知字段、类型不符、过期或代码/状态目录变化均拒绝。文档先复制为独立数据，不从保存 JSON 派发 argv 或加载类。公共 apply 在真实生命周期验收前继续禁用。

在操作锁及真实 dpkg frontend lock 内重新扫描、探针、模拟和生成完整审阅；除时间/原始观察标识等预期变化外，操作内容、绑定、门禁、目标、影响范围、维护合同必须一致。仅能排除 /proc/locks 中确实属于当前 PID、匹配已打开 FD 的完整 POSIX frontend 锁；其他持锁者仍阻断，丢失锁也阻断。持锁复核完成后再次检查过期。

类型化步骤只升级实际变更集合对应的认证归档。安装/重启预算使用 monotonic 时间，子命令共用剩余预算；超时不声称撤销已发给 systemd 的工作。安装后核对精确版本/归档字节、厂商下界、全新实例、当前控制定义、只读配置视图、所有可见目标文件持有者及每个已声明探针。有效配置/路径变化、未退出旧实例、额外消费者、健康或时效失败均不能返回修复通过。扩展名称摘要必须保持一致；唯一已审阅的 INI 新增见 3G.2，不把指令或扩展摘要当独立补丁认证。

成功仅为 VERIFIED_WITHIN_DECLARED_SCOPE，safe=false；失败沿用 PARTIAL/RESTART_REQUIRED/FAILED 审计，保存原确认 hash 和私有日志。同一计划不得重试。受控 runtime 定义/快照保持可审计，结果返回原签名所有权收据，清理由明确的 retire-preparation 操作处理；不自动回滚。

四格 VM 在当前版本的 no-change 审阅之后，从已验证的官方 base pocket 归档建立旧版 fixture，然后验证真实同分支升级。第二轮仅在重启后让显式探针访问不可用 loopback 端口，要求已升级包加健康失败结果为 PARTIAL；另验证错误确认和禁止同计划重试。旧包 setup 的 allow-downgrades 只存在于受保护的 disposable 测试脚本，生产执行器不提供该操作。所有 fixture Web listener 绑定 loopback，不使用漏洞利用。

## 3G.2 精确识别已审阅的新增 INI 指令

真实隔离诊断确认：从官方 base 升级到修复版后，仅新增 memory_hard_limit_percent，没有其他指令变更。已复核 [PHP 8.3.36 main.c](https://raw.githubusercontent.com/php/php-src/php-8.3.36/main/main.c) 的注册和 OnChangeMemoryHardLimitPercent：默认以 NULL 注册，对应 -1 的默认算法；[官方问题 #24497](https://github.com/php/php-src/issues/24497) 也记录了默认值显示为空的行为。此处没有修改 memory_limit 或新指令。

collector 协议更新为 2，同时返回全量设置摘要、仅排除这一个已审阅指令的基线摘要，以及该指令的 ABSENT/VENDOR_DEFAULT/明确数值分类。任意其他配置值继续只返回汇总摘要，不返回秘密或每个配置项的值。旧 collector/收据必须重新部署与准备。

修复后只允许 ABSENT→VENDOR_DEFAULT 这一新增情形，且原有设置基线、INI 路径和扩展名称摘要全部相同。新增非默认值、已存在值变化、删除指令、其他设置/模块变化或未知分类继续 UNKNOWN/PARTIAL。这个精确策略写入确认合同，并保留完整新旧摘要；指令存在本身从不证明补丁，包/文件/新实例/视图/内核请求等独立门禁仍必须通过。

## 3G.3 基础版到当前版的第二项确定差异

jammy 的实际旧→新诊断只新增 max_multipart_body_parts；noble 的对应差异为 memory_hard_limit_percent。已核对 [PHP 8.1.33 注册代码](https://raw.githubusercontent.com/php/php-src/php-8.1.33/main/main.c)：前者默认值为 -1。collector 协议 3 将这两项分别分类，允许各自或同时从 ABSENT 到 VENDOR_DEFAULT，其余设置基线、输入路径和扩展名称必须一致。

已存在的任一值不得变化，新增显式非默认值、未知字段或未审阅指令仍阻断。两个参数都不被写入；这些观测只解释精确的配置演进，不替代安装来源、修复版本、新实例和请求证明。旧协议及旧收据需重新生成。

## 3H 公开入口准备（发布门禁仍关闭）

`apply <managed-review.json> --confirm-sha256 <plan_sha256>` 的固定参数和能力边界已实现，但 release_gate.PUBLIC_REPAIR_ENABLED 仍为 false；没有环境变量、--yes、--force 或保存文档字段能覆盖该门禁。原无参数 apply 继续无 I/O 地拒绝。只有原生矩阵验收完成后才能切换维护者门禁。

启用后的路径只接受 schema 5 managed review，经内部事务桥重新验证；错误/缺失确认、重复 JSON key、NaN/Infinity、未知字段和能力缺失都不能执行。注入 reader 必须另外显式注入 package controller、simulator、probe 和 journal，即使它继承 LocalSystem。成功返回 0 只代表声明范围验证通过，所有失败/部分结果均不等于安全。
