# 原生复核诊断 / Native revalidation diagnostics

范围：明确重启重装包后的 Debian Apache 测试基线，保留生产对已删除模块的阻断；为持锁复核增加 admission/blockers、变化字段名和期限缩短诊断，不输出配置值，不放宽相等性判断。

Validation: local suite recorded in pytest.log/JUnit; native acceptance is CI_PENDING. Previous source 4c53acc, Actions 39881542701: 13/17 PASS, 4 FAIL. Ubuntu 22.04 both SAPIs and Debian 12/13 FPM passed actual upgrade/fault lifecycles. Debian Apache retained old deleted modules after fixture reinstall; Ubuntu 24.04 stopped at locked revalidation before installation, without enough diagnostics. Raw failed logs are retained here.

限制 / Limitations: public apply remains disabled. No developer-host package/service changes. This checkpoint does not certify the remaining four native cases.
