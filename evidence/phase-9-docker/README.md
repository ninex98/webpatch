# 阶段 9：Docker 自动发现与逐容器检查 / Automatic Docker inventory

2026-10-23（Asia/Shanghai）。**本地验收 PASS；新提交远端 CI 为 NOT_RUN，公开发布 NOT_RUN。** 此为 CI 待验收检查点，不宣称已完成远端安全矩阵或已更新公开 0.2.0。

问题：PHP 部署在 Docker 时，原宿主扫描只显示空清单和泛化的“进入容器扫描”，不能指出哪个容器运行 PHP。开发版 `webpatch scan` 现在自动读取一个本机 Docker daemon，逐个列出容器、镜像、PHP 软件包/自定义路径/头文件版本/进程名称，提供对应下一步。宿主机和容器证据分开，发现低于厂商修复线的容器包会影响 scan 总体提示和退出码，但不会进入宿主机修复计划。

范围与验收标准：独立可注入的 GET/HEAD 能力；不执行容器内代码、不安装扫描器、不重启/变更生产容器；固定路径及有界数据读取；多容器、停止、无 PHP 线索、权限拒绝、连接/超时/限额/损坏数据、扫描中集合变化均可见；自编译/Alpine/过期规则继续 UNKNOWN；容器元数据不授予自动修复；中文终端和 JSON 均能使用。发行版阈值、来源、审阅时间和有效期未修改。

| 检查 / Check | 当前结果 / Result |
|---|---|
| 全套 Python 3.10 fixtures | **PASS，696 passed**，零失败/错误/跳过；pytest.log / pytest.xml |
| Docker 新边界与编排用例 | 包含在上述全套中；49 项覆盖真实 Unix HTTP、tar 安全边界、CLI 自动接入、宿主计划仍 BLOCKED 等 |
| 原生 Docker API | **PASS，4 个独立 disposable 容器**；native.log / native-report.json / native-result.json |
| 真实 PHP-FPM 进程与官方 PHP 镜像头文件 | **PASS**；php:8.3-fpm-alpine 中观察到 `/usr/local` 安装、头文件版本和进程名；版本只作为未认证线索 |
| 发行版包与版本比较 | **PASS**；Ubuntu jammy 包读取；实际 dpkg 比较仅在测试容器中执行，不修改开发宿主 |
| 只读状态 | **PASS**；两次扫描前后 State（含 PID/StartedAt）、RestartCount、image、readonly flag、docker diff 完全一致 |
| 中文输出 | **PASS**；native-zh.txt，按容器给出结果、路径、包版本及后续动作 |
| .deb 构建及安装后入口 | **PASS**；package-build.log / installed-result.json；隔离 readonly+no-network 容器中已安装 CLI 返回 UNKNOWN/2，正确不跨出当前容器 |
| 新增 GitHub Docker discovery job | **NOT_RUN**，已配置，可在后续授权 push 后验证 |
| 本次完整远端安全矩阵 / 发布 | **NOT_RUN**；没有推送，没有覆盖 Release 或 tag |

本机测试命令：

```sh
.venv/bin/python -m pytest --cov=webpatch --cov-report=term --junitxml=evidence/phase-9-docker/pytest.xml
.venv/bin/python scripts/check_docker_scan.py --package-image webpatch-phase1:jammy --custom-image php:8.3-fpm-alpine --empty-image webpatch-ui:noble --socket /Users/ninex/.docker/run/docker.sock --output evidence/phase-9-docker
```

原生脚本仅读取本次创建的四个容器。三个运行（其中官方 PHP 镜像启动真实 FPM），一个保留为 created；另两运行容器使用 sleep 固定生命周期。生产扫描代码没有 exec 能力；测试比较器通过测试专用注入在 disposable Ubuntu 容器执行精确的 `dpkg --compare-versions`，验证真实发行版比较语义。宿主 inventory 使用固定空 fixture，原生 Docker 读取和 CLI 编排/JSON/终端均使用本次源码；不是对开发宿主或用户服务器进行全量生产扫描。无宿主 root/proc/socket mounts，无 privileged，所有临时容器已删除。

安装验证镜像 `webpatch-docker-discovery:verify` 以已有项目测试镜像为基础，在禁网构建中 COPY 当前源码和 docs，构建 .deb 后在镜像内 `dpkg -i`；容器运行时 read-only、no-network、cap-drop ALL、no-new-privileges。生成的二进制包未进入 Git，package-artifact.json 保存包和镜像 SHA256。

开发过程发现并修复了一项既有中文输出断言不兼容，以及 macOS fixture 临时 Unix socket 路径过长导致的 7 个 setup errors。前者恢复兼容短语并加宿主机作用域前缀；后者用短路径私有临时目录。最初终端输出未单独重定向，development-observations.txt 仅保留观察摘要，不伪装完整原始日志。最终完整检查见新 pytest/JUnit。首次公开镜像拉取等待本机 credential helper，已取消该次操作；随后使用临时空 Docker 配置匿名拉取，image-pull.log 保存成功结果，没有修改全局 Docker 配置。

当前远端基线也单独核实：`remote-baseline.json` 记录基线 `2af91b8` 的分发工作流成功、安全工作流失败（Debian 13 FPM/Apache 两格）。这些是旧提交的状态，不作为本阶段通过证据，也未宣称本次已修复它们。

边界：默认一个本机 daemon、至多 64 容器、45 秒预算；远端 context、其他 daemon、Kubernetes/containerd、任意自定义路径、无证据的运行映像与 Web 路由不保证覆盖。停止的容器只检查存储的元数据。Alpine 和自编译 PHP 不新增漏洞判定规则。头文件和包版本达标都不证明实际补丁安全，所有 safe 字段仍为 false。已有设计/修复规则与发布有效期保持原样。
