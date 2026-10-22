# 阶段 2C / Real APT simulation — CI 待验收

范围：为 Ubuntu jammy/noble 认证的同分支精确候选执行真实 apt-get --simulate --no-remove --only-upgrade，独立临时 APT_CONFIG 禁用系统 hooks/缓存写入。来源、preferences、dpkg status、extended_states 来自当前系统；被省略的 hooks/特殊配置保留阻断项，不能据此执行实际修复。

完整解析 Inst/Conf/Remv 并交叉核对摘要计数、架构及 configure 集合；移除、降级、重装、新依赖、跨分支/发行版、候选漂移和未批准依赖改变均阻断。列出服务及 maintainer scripts 可能产生的中断，人工恢复需预先验证快照/备份，不承诺自动回滚。

计划 schema 2 使用冻结模型，绑定 boot/machine/namespace 作用域、规则、包、源、索引、缓存归档、配置和运行实例摘要；检查活动包管理锁、模拟前后状态、进程复用/新增及 30 分钟上限。verify-plan 只比较不可信 JSON 中的数据，重新扫描/模拟并检测摘要、过期、状态和求解漂移，绝不执行保存的命令。所有计划仍 BLOCKED/executable=false，apply 禁用。

本地 Python 3.10：242 tests PASS；bash syntax PASS；日志/JUnit/源码摘要同目录。CI 需要四格 VM 上真实模拟、保存计划再验证、真实系统状态不变，以及 real APT + synthetic older status 的目标/依赖更新解析。合成状态单独放临时目录，真实 dpkg status 与运行二进制不改变；不是旧漏洞环境或实际升级测试。当前 CI NOT_RUN，不宣布阶段完成。

限制：实际执行/服务重启/修复后应用健康验证 NOT_RUN 且不在本轮授权范围；未知身份、未知/动态应用路由、loaded configuration、第三方及镜像列表阻断；容器为重建建议；Debian APT 修复规划不支持。PASS 仅说明模拟命令和解析成功，绝不表示运行时安全或可以执行计划。

首次 CI：Actions 39745983007（8a0f098），两版 Python 各 242 tests 和三组 Docker PASS；四格真实 APT 模拟均 PASS，但保存计划的再次验证均误报 PLAN_INPUT_STATE_DRIFT，故四格 VM 总门禁 FAIL。first-ci/ 保存完整报告、日志与摘要。对比扫描与计划 bindings，唯一变化为整个 /proc 目录列表：下一次扫描自身 PID 不同被错误纳入稳定摘要。

修正：稳定输入排除 /proc 根目录列表，PHP/Web 进程集合与 starttime/path 的单独前后检查继续保留。新增普通进程变化不误报、新 PHP 进程仍阻断测试；同时固定模拟临时目录父路径 /tmp，避免继承 TMPDIR 内容进入 APT 配置。本地 243 tests PASS，见 retry-local.log/xml 和 retry-local-manifest；四格 VM 必须重新验收。

第二次 CI：Actions 39747726821（40b7169），四格真实系统模拟与 verify-plan 均 PASS；后续 synthetic status 测试因仅降低目标/common 而使同源兄弟包精确依赖不一致，APT 正确拒绝，四格 VM 总门禁仍 FAIL。second-ci/ 保存完整证据。

升级求解修正：合成状态统一调整同 PHP 源码包的版本及精确依赖，保持一致；禁止改动真实 dpkg status。进一步在本地隔离容器发现 --no-download 在 simulate 下仍要求已缓存 deb，导致空缓存升级求解失败。移除该多余选项，固定 --simulate 仍然不会执行/下载（[官方 APT 手册](https://manpages.debian.org/bookworm/apt/apt-get.8.en.html)）；未加入 fix-broken、ignore-missing 或任何强制选项。原失败见 solver-jammy-first.stderr。

Ubuntu 22.04/24.04 arm64 真实 APT 升级求解 PASS，各输出 6 个 PHP 目标/同源依赖变化。使用已有阶段一测试镜像加当前源码构建派生镜像，运行参数 --read-only --network none --cap-drop ALL --security-opt no-new-privileges --tmpfs /tmp:rw,noexec,nosuid,size=64m；无宿主挂载、无特权模式、无联网或真实升级，临时副本写入仅在容器 /tmp。输出、构建日志、镜像身份和源码/制品摘要见 solver-*；本地 243 tests PASS。最终四格 amd64 VM 仍需重跑。
