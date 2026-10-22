# 阶段 2B.1 / Source policy audit

范围：严格解析 sources.list/deb822，识别 Signed-By/不安全选项、官方同发行版 pocket、第三方/混合源、pin、hold、dpkg 异常状态及 hooks/配置覆盖。仓库 URI 凭据不进入报告。只读取，不刷新 APT 缓存。

官方公告已重新核对：PHP、Ubuntu 两 CVE/USN-8948-1/-2、Debian 两 CVE；修复边界不变，有效期未延长。访问摘要见 official-review.json，规则文件摘要与历史基线相同。

本地 Python 3.10：184 tests PASS，JUnit/日志与源码摘要同目录；配置/策略解析通过不代表来源认证，成功状态明确为 POLICY_CHECKED_NOT_AUTHENTICATED。密码学身份链由下一小阶段实现。此阶段新增门禁均由严格注入 fixture 验证；实际系统覆盖随 CI 回归检查，当前为 CI 待验收。
