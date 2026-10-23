# Debian 独立验收 / Independent Debian acceptance

源码 `2d8132c831297a7254a500ce6d8a3c2412f0b77a`，Actions [39883475413](https://github.com/ninex98/webpatch/actions/runs/39883475413)。六个 Debian job 全部 PASS：12/13 两格归档认证及 12/13 × FPM/Apache 四格独立 QEMU 客体。取证时整轮 Ubuntu job 仍在运行；本记录不声称全矩阵通过。

四格各自验证官方 base→fixed 同分支升级成功、精确确认拒绝、禁止重试、以及真实升级/重启后的 loopback HTTP 失败返回 PARTIAL。lifecycle-results.json 是八个事务原文的明确字段摘录，包含原制品 SHA256、精确版本和核对结果；原始审计/日志、环境/镜像/源码清单保留。validation.json 列出全部下载制品摘要与选存映射，重复完整 scan/plan/report 不另复制，原文可由对应 Actions 获取。

Validation: all eight transaction states and six job conclusions checked; every implementation file matches the tested commit at evidence collection. Artifacts contain no private keys, guest disks or binary packages. Debian image HTTPS/SHA512 integrity is distinct from image-signature attestation (NOT_AVAILABLE); APT trust is verified independently.

限制 / Limitations: amd64 official Debian 12/php8.2 and 13/php8.4, standard FPM/mod_php, finite declared scope only. Public apply still disabled pending complete Ubuntu/CLI acceptance. No host/production repair, exploits, automatic rollback or broad safety claim.
