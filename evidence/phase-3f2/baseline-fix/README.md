# 统一审阅基线修正 / Managed-review baseline correction

首轮 a6f810f 四格 VM FAIL，fixtures/三个包容器/两格 Node PASS。noble 检查明确阻断 phpdbg 身份缺项和 /usr/share/man-db/chconfig 文件身份；jammy 的旧 php8.1 元包版本已不在当前仓库，下载失败。原始 noble/fpm、jammy/apache 日志附后。

代码核实发现 authenticate 的 SAPI 过滤遗漏了已发现的 phpdbg 包。现在只补充其官方 archive/file 身份核对；phpdbg 风险/服务支持仍 UNKNOWN，不能当受支持 Web SAPI。触发器执行文件的 UNKNOWN 同时输出观察到的 hash/owner/mode，便于区分缺失、权限和内容差异。

临时 VM 在进入受控维护证据前，把整个现有 PHP 源码组更新到当前官方版本并 reinstall payload，同时重装 libc-bin/man-db，以建立明确的完整官方正例；保存原有版本集合。产品不自动重装或修复这些环境问题，文件身份/权限门禁未放宽。本地 548 tests PASS；日志/JUnit/源码摘要在本目录，云端待重验。
