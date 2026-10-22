# 阶段三：有限修复前置接口 / Phase three prerequisite interfaces

## 3A.1 部署清单核对

`webpatch deployment-manifest --format json > deployment.json` 导出当前观察集合；`webpatch verify-deployment deployment.json --expect-sha256 <manifest_sha256>` 重新扫描并逐项核对。两者退出码为 4，不授予执行权限；参数/读取失败沿用 CLI 错误语义。默认 scan 行为不变。

清单 schema 1 绑定当前 scope、规则、输入摘要、包/运行实例/服务/pool/route/安装路径的独立实体与事实；有效期受扫描、规则和认证索引时效限制。missing、unexpected、changed 明确区分消失实体、新增实体与事实变化。重复 ID、额外字段、错误/重算摘要与固定审阅 hash 不一致、过期、范围或规则变化均拒绝；重算摘要不能掩盖从清单删除仍在扫描结果中的消费者。

`MATCHED_OBSERVATIONS` 仅说明清单与当前观察集合一致。导出文件不是独立部署发现来源，不能证明穷举；completeness 固定 UNPROVEN，authorization 固定 NONE，空清单也不构成完整覆盖。调用者自行写 COMPLETE/approved 字段不会解除门禁。这是后续显式应用证据、操作者审阅和有限执行输入的一项核对接口，不替代实际证明。

后续 3A.2 将实现独立的显式应用证据能力，在受限 VM 中验证 challenge、来源、进程与配置/请求归属；默认 scan 不执行该能力。
