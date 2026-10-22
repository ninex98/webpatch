# 2D.1 结构化覆盖与作用域 / Structured coverage and scope

PASS: `.venv/bin/python -m pytest -q --junitxml=evidence/phase-2d1/pytest.xml`，303 tests；`git diff --check` PASS。manifest.json 保存当前源码 SHA256、Python/平台及日志/JUnit 摘要。head 是测试时父提交；源码哈希绑定本次待提交内容。

实现独立实体要求判断：安装文件、运行实例/服务、配置观察、自定义安装、缺失适配器和失败读取。保留旧 coverage_gaps；schema/迁移见 docs/phase-2d.md。目标选择仍列出完整扫描及同包所有消费者；未知影响范围保持阻断。测试含全部环境 fixtures、多进程共享包、权限错误、外部 namespace、空清单和旧计划迁移。

GitHub/真实环境针对本阶段的新源码尚 NOT_RUN；2D.1 的本地模型验收通过，四格 VM 的运行证据验收属于后续 2D.2/2D.4。没有加载配置/HTTP 归属证明；实际修复 NOT_RUN_DISABLED。

English: The entity model and selection/impact contract pass local fixtures. Current-source hashes bind these results. Runtime configuration/request attribution and real-environment validation remain pending; repair is disabled.
