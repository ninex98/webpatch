# 4A 容器重建建议 / Container rebuild advice

本地 500 tests PASS：镜像摘要输入、逐 CVE 厂商约束、空清单/宿主/自定义安装/过期/未知规则与 CLI 无执行能力。源码、日志/JUnit/制品摘要见本目录。

CI pending：三格只读、禁网容器中执行安装后的 rebuild-plan 并核对扫描前后配置/APT/dpkg 状态不变。此阶段交付原设计中的重建建议；未运行镜像构建/发布/rollout，明确 NOT_RUN。声明的镜像 digest 不是自动认证的部署身份，safe=false。
