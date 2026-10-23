# 3G.2 已审阅 INI 新增 / Reviewed INI addition

6ca6ae2 的真实诊断：changed=[]、removed=[]，只 added=[memory_hard_limit_percent]，见 original-difference.json。复核 PHP 官方修复版本的注册代码和默认显示问题，资料链接见 docs/phase-3.md。

本地 593 tests PASS。允许这一个指令以已审阅默认语义新增，同时保留全量和其余设置的独立摘要；非默认新增、旧值变化、其他配置/路径/扩展变化及旧协议均拒绝。没有修改任何内存参数，也不以指令存在判断补丁。

collector v2 的实际回调及四格升级/故障重验 CI pending。源码、日志/JUnit/制品摘要在本目录；此前 PARTIAL 记录未改成 PASS。
