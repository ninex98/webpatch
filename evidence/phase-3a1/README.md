# 3A.1 部署清单核对 / Deployment reconciliation

本地 PASS：354 tests；pytest.log/xml 和 manifest.json 绑定本次源码/平台。新增正例与空清单、增删实例、配置/包/作用域/规则变化、摘要篡改、过期、伪造完整性、重复实体和固定审阅 hash 反例。CLI 不调用模拟器或执行器。

CI 待验收 / CI pending：推送后复用已有 Python、Docker 和四格 VM 回归。此小阶段只证明观察集合核对，不证明部署清单穷举或实际 loaded config/request attribution。apply 仍拒绝，实际修复 NOT_RUN_DISABLED；开发宿主未修改。

English: Matching declarations are explicitly UNPROVEN for completeness and never authorize repair. Local reconciliation tests pass; full cloud regression follows the checkpoint.

后续云端回归：Actions 39767703025 对 a0d63da 全部 9 项 PASS（Python 3.10/3.12 各 354 tests、三格 Docker、四格 Ubuntu VM）；结果对应此检查点源码，不代表后续新代码自动通过。
