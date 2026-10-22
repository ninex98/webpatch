# 结构化 systemd 属性 / Typed systemd properties

此前 bd39f76 重验的 FPM 两格仍 FAIL（完整日志附后）；systemctl 的 EnvironmentFiles 专用数组打印器对空数组不产生输出，即使 --all。新增固定只读 busctl get-property，必须明确获得 `a(sb) 0`；失败/未知/非空均阻断。其他单值与字符串数组仍要求显式字段。记录属性名以便诊断，不读取环境变量值。

参考：2026-10-23 审阅 https://github.com/systemd/systemd/blob/v255/src/systemctl/systemctl-show.c 的 EnvironmentFiles 分支。

当前源码本地 470 tests PASS，新增空数组、非空、失败与 allowlist 边界。日志、JUnit、源码摘要见本目录。修正后的四格真实服务重验 CI pending；不得以本地 fake 证明服务重启通过。
