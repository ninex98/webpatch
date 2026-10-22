# 阶段四扩展 / Phase four extensions

各扩展独立验收，不由 PHP 主机修复的通过结果推断其他环境已支持。

## 4A 容器镜像重建建议

在目标容器内部运行 `webpatch rebuild-plan --image registry.example/team/php@sha256:<64位摘要> --format json`。命令只扫描当前 namespace 并生成建议，退出 4；不会连接 Docker/containerd socket、构建、推送、滚动发布或原地安装。默认 scan 不变。

建议 schema 1 绑定当前 scope、scan/rule 摘要和有效期，逐个 engine/逐个 CVE 列出发行版源码包修复下界和官方来源。image@sha256 是操作者声明的不可变标识，字段明确 DECLARED_NOT_AUTHENTICATED_BY_LOCAL_SCAN；不把任意调用者字符串当实际运行镜像身份。tag-only、命令形状/无效摘要输入拒绝。

顺序包括定位和认证构建来源、同分支重建并记录精确依赖/归档/镜像摘要、扫描新镜像、canary/滚动替换全部相关实例与任务、应用请求及新实例归属验证。恢复由经过审阅的部署流程负责，不承诺 APT 回滚。原扫描覆盖缺口继续展示，safe=false；ADVISORY_READY 仅指可提供已知厂商约束，build/rollout 均 NOT_RUN。

宿主扫描、空 engine 清单、未知厂商规则、过期证据、自定义安装或不明 scope 均给出可行动的 BLOCKED_ADVICE。镜像构建系统、registry provenance、任意编排器与生产业务验证不在此建议接口的自动能力中。实际自动镜像发布不是原设计本项“镜像重建建议”的交付承诺。

验收：本地正反例及 Ubuntu 22.04/24.04、Debian 12 的真实只读/禁网容器接口检查，验证前后配置/APT 状态不变。当前结果以 evidence/phase-4a 和对应 CI 为准。

## 后续扩展

Debian 修复须独立认证签名根、仓库时效、维护行为和实际升级/失败路径；当前检测支持不等于可执行修复。Node.js 使用独立 runtime adapter/RuleProvider，不把 PHP 的 SAPI 或 dpkg 回移植规则套到 upstream Node 版本，npm 依赖风险另行处理。

## 4B Node.js 独立发现与规则

`webpatch scan-node --format json` 使用独立 NodeAdapter 与 NodeRuleProvider，复用 SystemReader、scope、Package/RuntimeInstance/Evidence/Report 模型；默认 PHP scan 不变。只读 dpkg 元数据和 procfs，不执行 node/npm、不读取应用配置/进程环境、不进行 npm 依赖审计。通过可见进程执行路径也能发现改名的 node；常见 /usr/local、/opt、snap 路径作为自定义安装线索。

本项支持矩阵：Debian 12/bookworm 和 13/trixie 的 nodejs 源码版本对照覆盖 CVE-2026-21714 与 CVE-2026-48618；libnode 库单独列出本地映射/文件观察。Ubuntu 可发现但没有本次审核的版本规则；NodeSource、nvm、自编译、upstream tarball/其他版本族、其他 OS 和隐藏进程保持 UNKNOWN，不自动修复。这不是完整 Node CVE catalog。

规则于 2026-10-23 Asia/Shanghai 审阅，UTC 2026-10-22T19:55，至 2026-10-29T00:00 UTC 到期；PHP 规则日期未改。Debian 两项修复下界分别为：bookworm 18.20.4+dfsg-1~deb12u2 / u3，trixie 20.19.2+dfsg-1+deb13u2 / u3。使用 dpkg 比较源码版本，允许经身份核对的 binary binNMU 后缀，不使用 upstream SemVer 覆盖发行版回移植版本。

来源：[CVE-2026-21714](https://security-tracker.debian.org/tracker/CVE-2026-21714)、[DSA-6272-1](https://security-tracker.debian.org/tracker/DSA-6272-1)、[DSA-6183-1](https://security-tracker.debian.org/tracker/DSA-6183-1)、[CVE-2026-48618](https://security-tracker.debian.org/tracker/CVE-2026-48618)、[DLA-4809-1](https://security-tracker.debian.org/tracker/DLA-4809-1)、[DSA-6517-1](https://security-tracker.debian.org/tracker/DSA-6517-1)。逐 CVE 来源存于独立 nodejs.json，未从 PHP 公告推导 Node 风险。

VERIFIED_LOCAL_FILE_ASSOCIATION 只表示稳定执行文件和本地磁盘/package owner 关系；libnode 映射与磁盘文件分别保留，未认证的库加载身份不能升级为已修复。厂商归档身份、完整发现和应用健康/路由仍为覆盖缺口；任何包版本达标都保持 runtime_status=UNKNOWN、safe=false。空清单不是 Node 不存在证明。两格独立 Debian 容器会核对真实 dpkg 比较、改名 Node 进程、包中源码一致性及只读状态不变，无漏洞利用。

## 4C.1 Debian 归档认证链（CI 待验收）

Debian 12/bookworm 与 13/trixie 增加独立只读来源策略和归档认证。首个范围为 deb.debian.org/ftp.debian.org 的 codename main 仓库，以及 deb.debian.org/security.debian.org 的对应 debian-security main 仓库；stable/testing 别名、混合 codename、第三方地址、其他组件或自定义 keyring 仍明确阻断。

使用固定 debian-archive-keyring.gpg，并按发行版区分 archive/release/security 主钥指纹。GnuPG VALIDSIG 的签名子钥必须归属已固定的主钥，不能把任意本地 keyring 条目当信任根。Debian 的 Suite 使用已审阅 stable/oldstable 标签，而 Codename 必须精确匹配 source suite；security Label 单独为 Debian-Security。更新/security pocket 要求 Valid-Until，且 Date 不超过七天；base 仅用于签名快照身份，不作为新鲜修复候选。

主钥资料于 2026-10-23 Asia/Shanghai 审阅：[Debian FTP archive keys](https://ftp-master.debian.org/keys.html)、[Debian security FAQ](https://www.debian.org/security/faq)。官方邮件公告链接已记录，但本轮读取返回 403，不能声称成功阅读；真实测试进一步用官方镜像内 debian-archive-keyring 和实际 InRelease 签名交叉验证指纹，保存 keyring 版本及哈希。没有自动下载/导入新信任根。

两格独立 Debian 容器验证真实 Release→Packages→缓存 deb→已安装 FPM 文件、篡改签名拒绝和状态不变。根文件系统只读且禁网，负例只写独立 /tmp tmpfs。此阶段没有扩展 Debian 的执行准入；准备、规划和真实升级生命周期仍须独立完成。

## 4C.2 独立 Debian VM 基础验收（CI 待验收）

GitHub 临时 Ubuntu runner 内用 QEMU 启动 Debian 12/13 genericcloud 客体，各自验证 FPM/Apache。没有 privileged Docker、9p/virtfs、宿主 root/proc/socket 挂载；源码只通过 loopback SSH 导入，逐文件比对从受测 Git commit 导出的 SHA256。客体使用独立磁盘、kernel/systemd/procfs 和当前官方 main/security APT 来源。

镜像来自 cloud.debian.org 的官方 HTTPS，并核对同目录 SHA512SUMS；当前目录不提供镜像签名，因此记录为传输/内容完整性，明确 NOT_AVAILABLE，不声称签名镜像认证。这个测试平台信任边界独立于产品必须验证的 APT Release/Packages/deb 认证链。保存镜像 URL/hash、加速类型、kernel、服务状态和源码导出清单，不上传磁盘、SSH 私钥或私有状态目录。

本阶段只验收客体启动、实际 systemd PHP 服务发现和认证文件身份；还没有把 Debian 加入准备/执行准入。主/客体脚本都有运行环境守卫，客体另需唯一 marker；本地测试只验证拒绝误运行，不启动 VM 或安装工具。后续在同一隔离边界内独立完成 Debian 升级/故障生命周期。
