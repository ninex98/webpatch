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

`scan` 不需要 root；受限读取显示为覆盖缺口。阶段一只查询 dpkg、读取系统身份/常见目录/有限 proc 元数据，不执行 PHP，不访问网站或 Docker daemon，不更新 APT 缓存，不重启服务。

`plan --dry-run` 生成**阻断式建议**，明确 `apt_simulation=NOT_IMPLEMENTED`，不代表已经运行 APT 模拟。`apply` 始终拒绝，没有 `--yes` 绕过开关。

| 退出码 | 含义 |
|---|---|
| 0 | 仅帮助/版本等成功操作；当前 scan 不返回 0 |
| 1 | 观察到包版本低于匹配的厂商修复边界，潜在受影响 |
| 2 | UNKNOWN / 覆盖不完整；参数错误也由 argparse 返回 2，查看 stderr |
| 3 | 扫描无法完成，例如损坏规则数据 |
| 4 | 修复计划或执行被阻断 |

JSON `schema_version=1`；包含 OS/作用域、独立二进制包和源码包版本、运行时线索、每 CVE 的版本对照、官方引用、证据摘要及覆盖缺口。证据摘要用于追踪本次输入，**不等于来源签名或远程证明**。不记录进程环境、命令行、完整配置或仓库凭据；路径/包名仍属于运维信息。

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

[GitHub Actions](.github/workflows/ci.yml) 包含 fixtures、Docker 和 Ubuntu 临时 VM 服务冒烟测试。该目录发布为独立仓库后工作流才会生效；不能在开发者宿主运行 VM 安装脚本。当前执行证据和未运行项见 [阶段一验收记录](evidence/phase-1.md)。

## 贡献边界

新增适配器须声明发现/判定/规划/执行能力及未覆盖情形，提供失败路径 fixtures 和对应的真实环境集成验证。不能把未发现、查询失败、版本字符串相同或安装成功当成安全。涉及修复的贡献必须先完成设计文档中的阶段二与阶段三门禁。
