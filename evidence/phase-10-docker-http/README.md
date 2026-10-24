# Docker HTTP 响应结束兼容性 / Docker HTTP response completion

2026-10-24 Asia/Shanghai。**本地 PASS，远端 CI 待验收。**

首次 0.3.0 安全 run 40055671792 的 Python 3.12 fixtures 与原生 Docker 检查失败。HTTPResponse 在读完 Content-Length 后可能释放最后一个 socket 引用；原循环再次 settimeout 触发 EBADF，把已完整读取的 os-release、头文件或进程清单误记为连接失败。initial-fixtures.log、initial-native.log 保留该次原始 CI 日志。

修正：读取循环在 response.isclosed() 时结束，保留超时、大小、HTTP 状态和 Content-Length 截断检查，不放宽任何缺证据/安全语义。原有真实 Unix HTTP 正反例无需修改即能覆盖这项回归。

验收：本地 Python 3.10 全套 **698 PASS**；Ubuntu 24.04 / Python 3.12 隔离只读禁网容器中 Docker 相关 **49 PASS**；真实 Docker 四容器检查 **PASS**。linux-build.log 记录项目测试镜像内安装 Python 测试依赖；初次忘记为 pytest 提供可写 /tmp 的失败保留在 linux-no-tmp-failure.log，随后仅加 32 MiB 私有 tmpfs 后通过。无宿主 root/proc/socket mounts，无 privileged。

为加强发布验收，Docker CI 还将在 GitHub 临时 VM 中构建并安装 .deb，实际调用 sudo /usr/bin/webpatch scan，核对四个受测容器的结果和扫描前后不变性。该入口有 hosted-only 守卫；本地 NOT_RUN，需新提交 CI 通过。不读取开发宿主的全部容器。
