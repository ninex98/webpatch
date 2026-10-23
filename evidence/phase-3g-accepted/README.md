# Ubuntu 内部修复基线 / Ubuntu internal repair baseline

源码 2d8132c831297a7254a500ce6d8a3c2412f0b77a，Actions [39883475413](https://github.com/ninex98/webpatch/actions/runs/39883475413) **17/17 PASS**。Python 3.10/3.12 各 605 tests；Ubuntu 22.04/24.04 × FPM/mod_php 四格真实 base→fixed 升级和重启后 HTTP 故障路径均通过。Debian 六格单独保存在 evidence/phase-4c-accepted；其他 Node/容器扩展也在同轮通过。

原始 Ubuntu 日志、审计、JUnit、包摘要、环境和选定小型模型保留；八个事务的精确版本、确认 hash、复核状态与后验结论以显式字段摘录写入 lifecycle-results.json。validation.json 包含全部下载制品 SHA256、受测源码摘要及留存映射；重复大型模型和二进制 deb 只记摘要，不加入 Git。

This certifies the internal typed transaction at exact source 2d8132c. It does not certify the subsequently enabled installed CLI. All successes remain VERIFIED_WITHIN_DECLARED_SCOPE with safe=false; actual post-restart request failures are PARTIAL with changed=true. No host/production repair or vulnerability exploit was performed.

后续 d314ead 的同代码复验有两格故障场景在安装前被 transient process/输入观察竞争阻断，成功升级场景通过；它不推翻本次记录，也不能被称作完整 PASS。后续夹具必须保存全部尝试，只对未变更的观察竞争生成新计划有限重试，不能重试同一计划或放宽产品门禁。
