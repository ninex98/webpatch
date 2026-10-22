# WebPatch

开源 Web 运行时安全检测 CLI，Python 3.10+、Apache-2.0。当前为 **0.1.0 只读预览版**，聚焦 PHP2Shell：CVE-2026-109618 / CVE-2026-109619。

先读 [架构、支持矩阵、测试矩阵与分阶段计划](docs/design.md)。当前不具备自动修复能力；`MEETS_VENDOR_FIX` 仅表示包元数据中的版本达到厂商公告边界，**不表示机器已安全**。每份报告的 `safe` 均为 false。

## 使用

```sh
# 在目标 Linux 上使用已构建的本地包；不需要 pip，也没有安装钩子或后台服务
sudo apt install ./webpatch_0.1.0_all.deb
webpatch scan
webpatch scan --format json
webpatch plan --dry-run --format json
```

`scan` 不需要 root；受限读取显示为覆盖缺口。扫描关联 dpkg 包、进程启动标识/namespace/映像、systemd 服务、FPM pools、mod_php 映射和静态 Web handler；不执行 PHP，不访问网站或 Docker daemon，不更新 APT 缓存，不重启服务。`VERIFIED_LOCAL_ASSOCIATION` 仅表示本地关联一致，静态配置仍不是已加载配置或应用健康证明。

Ubuntu 22.04/24.04 的官方直连源可验证已有 InRelease 签名和 Packages 摘要。用 `--package-cache /absolute/directory` 指定**事先获取**的 `.deb` 缓存，再核验完整归档、control 身份和磁盘运行文件；扫描不会下载。缺缓存、过期/损坏索引、不支持的镜像列表、第三方/混合源、未知身份保持 UNKNOWN。Debian 当前只提供官方漏洞版本对照。

`plan --dry-run` 对可认证的 Ubuntu 官方同分支候选运行真实 APT 模拟，并输出精确目标、全部依赖变化、服务中断提示和阻断原因。模拟使用独立临时配置，不执行系统 APT hooks、不更新索引、不安装包；系统 hooks、pin 和特殊配置仍作为阻断项展示。`apt_simulation` 区分 `PASS`、`FAIL`、`NOT_RUN`，模拟成功不表示计划可执行。移除、降级、新依赖、跨分支/发行版、不可信或未批准的依赖变化均阻断。容器只提供重建建议。

计划 `schema_version=2`，绑定规则、主机/启动作用域、包/配置/源/索引/运行实例摘要，最长有效 30 分钟且不超过规则过期时间。可以保存并再次核对：

```sh
webpatch plan --dry-run --format json > reviewed-plan.json
webpatch verify-plan reviewed-plan.json --format json
```

`verify-plan` 重新扫描、模拟并报告漂移，只比较保存的数据。**所有计划仍为 BLOCKED、executable=false，退出码 4；`apply` 始终拒绝**，没有 `--yes` 绕过开关。未知路由、已加载配置、应用健康及未覆盖运行实例仍阻止自动修复。无实际安装、升级、回滚或修复执行器。

| 退出码 | 含义 |
|---|---|
| 0 | 仅帮助/版本等成功操作；当前 scan 不返回 0 |
| 1 | 观察到包版本低于匹配的厂商修复边界，潜在受影响 |
| 2 | UNKNOWN / 覆盖不完整；参数错误也由 argparse 返回 2，查看 stderr |
| 3 | 扫描无法完成，例如损坏规则数据 |
| 4 | 修复计划或执行被阻断 |

扫描 JSON `schema_version=1` 增加运行实例、配置关系、软件源审计和包信任字段。包版本对照、密码学文件身份、本地进程关联和应用路由证明是不同层次。证据摘要用于追踪输入，**不等于远程证明**；固定签名指纹也不证明已被 root 入侵主机的完整性。不记录进程环境、完整配置或仓库凭据；路径/包名仍属于运维信息。

离线规则审阅于 **2026-10-22**，有效至 **2026-10-29 00:00 UTC**。过期或系统时间早于审阅时间时版本判定降为 UNKNOWN。没有自动在线规则更新；维护者必须重新核对官方公告、修改规则日期/版本、运行测试并发布，不能单独延长日期冒充审阅。上游版本仅供参考，不用于判断发行版回移植包。

## 开发与验证

在项目虚拟环境中安装，不修改系统 Python：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m pytest --junitxml=evidence/pytest.xml
```

Docker 隔离集成测试（分别替换 BASE 为 `ubuntu:22.04`、`ubuntu:24.04`、`debian:12`）：

```sh
docker build -f tests/integration/Dockerfile --build-arg BASE=ubuntu:24.04 -t webpatch-test:noble .
docker run --rm --read-only --network none --cap-drop ALL --security-opt no-new-privileges webpatch-test:noble
```

容器 build 内构建并用 APT 安装 `.deb`。测试不使用宿主目录挂载、特权模式、真实攻击请求或漏洞利用。构建脚本 `scripts/build_deb.py` 只构建包，在非 Linux 平台拒绝运行。`dist/` 中的包是本地安装制品；**尚无公开 apt 仓库**。

[GitHub Actions](https://github.com/ninex98/webpatch/actions) 已实际运行 fixtures、三组 Docker 和四格 Ubuntu 临时 VM 检查。不能在开发者宿主运行 VM 安装脚本。证据见 [CI 基线](evidence/ci-baseline/README.md)、[2A 本地关联](evidence/phase-2a/README.md)、[2B 源审计](evidence/phase-2b-sources/README.md)、[2B 身份链](evidence/phase-2b-trust/README.md)、[2C 模拟计划](evidence/phase-2c/README.md)。历史证据只证明其记录的源码；失败和待验收结果单独保留。

## 贡献边界

新增适配器须声明发现/判定/规划/执行能力及未覆盖情形，提供失败路径 fixtures 和对应的真实环境集成验证。不能把未发现、查询失败、版本字符串相同或安装成功当成安全。涉及修复的贡献必须先完成设计文档中的阶段二与阶段三门禁。
