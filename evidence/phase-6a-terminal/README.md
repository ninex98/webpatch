# 阶段 6A：人类可读终端 / Human-readable terminal

2026-10-23. 本阶段本地验收 PASS；最终组合版本 hosted CI / Release NOT_RUN，待后续引导修复阶段完成后验收。

范围：默认 scan/scan-node 显示结果、去重包版本/CVE、待核实项和下一步；--details 保留证据检查，--format json 与退出码不变。支持 --lang auto/en/zh、TTY 颜色、NO_COLOR、窄终端、控制字符/Bidi 转义。plan 默认即只读，无需手写 --dry-run。呈现层不改变风险决策或修复门禁。

安装器默认显示下载/验证/安装进度，--verbose 展开 APT 日志；APT 失败完整回显错误。仅公开发布的 deb 设为 0644、临时目录为 0711 供 _apt 遍历，日志/校验文件仍为 0600，避免私有目录导致的 unsandboxed 下载提示。未改变 APT/needrestart 的系统策略。

验收：630 pytest PASS（pytest.log / pytest.xml）；Ubuntu 22.04/24.04、Debian 12/13 arm64 disposable 容器各 22 场景 PASS（*-result.json）；静态 shell/diff 检查 PASS。已安装 CLI 中文空清单文本通过，exit 2，见 installed-scan-zh.txt。其余 empty/affected 文本为明确注入的 fixtures，不冒充真实有漏洞主机。源码与制品/环境摘要见 manifest.json。

当前截图里的无 PHP 情形明确显示 UNKNOWN、未发现包/运行时线索及无可供修复的包，不输出“安全”或编造可执行修复。所有安装测试只在隔离容器，无 host mounts/privileged；开发宿主 PHP/APT/服务未改变。
