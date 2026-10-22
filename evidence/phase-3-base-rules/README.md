# 官方基础版本识别 / Official base-version recognition

重新审阅 USN-8948-1（jammy/noble 修复下界未变）及 USN-8948-2（旧 ESM 系列，不纳入本次支持），并核对已有签名索引记录中的 jammy 8.1.2-1ubuntu2 与 noble 8.3.6-0maysync1。它们可按各自发行版规则报告 BELOW_VENDOR_FIX；元数据版本匹配仍不认证来源，safe=false。

基础仓库记录只用于已安装身份和旧版本识别，不提升为新鲜的可安装修复候选。修复下界及 2026-10-29T00:00 UTC 到期不变；bundle 记录本次审阅，旧计划因规则摘要变化必须重建。新增相似但未经审阅的 maysync2 反例。

本地时钟 fixture 调至此次审阅之后；未来索引日期反例相应保持真正位于未来。原本 clock fixture 更新后首轮 1 FAIL/521 PASS（固定写死日期不再未来），测试修正后结果见日志/JUnit。新增真实 dpkg 版本比较向量将在三格容器验证，CI pending。

来源：https://ubuntu.com/security/notices/USN-8948-1 、https://ubuntu.com/security/notices/USN-8948-2 ；签名基础仓库记录与历史证据定位见 base-index-provenance.json。历史索引记录只用于审阅不可变基础版本身份，绝非当前源码验收证据。
