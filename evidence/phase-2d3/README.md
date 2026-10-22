# 2D.3 统一计划门禁 / Unified plan review gates

最终结果 PASS：`d5447b3` 的云端 9 项全部成功，见 accepted-ci/；最终 2D.4 同样通过。以下 CI pending 段落记录检查点当时状态，不是当前结论。

本地 PASS：336 tests；日志/JUnit/源码及示例计划哈希见本目录。initial-pytest.log 保留一次旧测试期望不匹配（更严格的动作字段拒绝）；最终已保持摘要错误报告并新增语义检查。`git diff --check` PASS。

reviewable-fixture.json 是明确标注的合成 fixture：规则/认证/依赖解析门禁实际 PASS，READY_FOR_REVIEW；覆盖、安装等价性、维护行为和执行授权仍阻断。不是生产系统验收或修复结果。新增测试覆盖索引临近到期、陈旧扫描、时钟反向、重新摘要的过期时间/门禁/动作篡改、pin/hold/hooks/锁/依赖冲突，以及独立计划文件大小边界。

CI 待验收 / CI pending：本次必须重新运行 Python 3.10/3.12、Docker 三格与 VM 四格。首次 2D.2 CI 的四格 VM 因保存计划超过普通文本 1 MiB 限制失败，本阶段增加单独 16 MiB 计划读取接口，配置/procfs 限制保持。失败完整制品在 evidence/phase-2d2/first-ci；后续 CI 结果待保存。

English: Local review gates and tamper/expiry checks pass. The finite positive fixture remains non-executable. Full current-source cloud acceptance is pending; no install/restart executor exists.

后续验收 PASS：Actions 39763556960 对 `d5447b3` 的 9 项全部成功，完整日志/制品在 accepted-ci/；最终 2D.4 源码 `efb122d` 的 39763873264 同样 9/9 PASS。最终源码逐项核对见 ../phase-2d4/current-source-validation.json。门禁审阅完成不表示执行准入或安全状态。
