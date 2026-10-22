# 829df71 已验收基线 / Accepted baseline

Actions 39848034144 全部 11 jobs PASS：Python 3.10/3.12 各 522 tests，三格原生包/只读容器，两格 Node，以及四格 Ubuntu FPM/Apache 的受控启动、当前签名收据/请求复核和执行输入审阅。

这是 commit 829df71 的历史验收，明确关闭其 3D.2、3E.1、3F.1、4A、4B 范围；不代表之后的 3F.2/3F.3/3G 或 Debian 修复已通过。validation.json 逐项校验四格实际输出，并记录全部下载制品哈希。保留有关源码 manifest、环境、模型、日志/JUnit，省略重复的大型 scan/plan JSON 与生成 deb 本体；完整省略清单和哈希在 validation.json，不用旧证据证明新源码。
