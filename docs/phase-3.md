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
