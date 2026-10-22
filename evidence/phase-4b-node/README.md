# 4B Node.js / Independent Node extension

本地 519 tests PASS，新增 17 项覆盖两发行版/两 CVE 的独立边界、空/未知/重复/未配置/过期包、外部命名空间、执行映像删除/替换、改名进程及 CLI。8 个 dpkg 比较向量由真实 Debian 12/13 容器另行验证，避免用自身版本实现证明自身。

官方来源、审阅时间和到期边界见 docs/phase-4.md 与 src/webpatch/data/nodejs.json。规则只针对列出的两项 Node 运行时 CVE；Ubuntu/upstream/NodeSource/nvm 不冒用 Debian 结论，npm 未评估，safe=false。本地不运行 Node。

CI pending：两格独立 Debian 容器，read-only/network-none/cap-drop ALL/no-new-privileges；只运行无害改名 Node 定时器作为进程 fixture，不启用服务器或漏洞利用。测试后比较 dpkg 状态，输出模型、源码哈希及包内源码一致性。原 PHP/服务矩阵继续独立运行。
