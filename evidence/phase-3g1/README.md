# 3G.1 事务衔接 / Managed transaction bridge

本地 559 tests PASS，覆盖固定 schema/类型、精确确认、合同与证据篡改、来源变化、内核锁归属、类型化归档分派、同计划重试及旧包/旧 PID/缺配置证据不能通过修复后验证。桥接成功 fixture 显式注入最终 verifier，不能替代真实服务验收。

CI pending：四格 Ubuntu VM 的官方 base→fixed 实际升级、重启后真实 loopback HTTP 故障、确认/审计/重复尝试检查。测试会重建旧版本隔离环境，但无漏洞利用；监听仅 loopback。此时公开 apply 仍禁用，真实执行仅由受保护集成脚本调用内部接口。

日志/JUnit/源码摘要见本目录。成功仍只声明有限作用域，safe=false；无自动回滚，保留私有日志和所有权收据。
