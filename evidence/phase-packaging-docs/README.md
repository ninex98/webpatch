# 容器文档安装夹具 / Container documentation fixture

ba5d9f6 的 Actions 39885894353：八格已安装公开 CLI 真实升级/故障、两版 Python fixtures、Node 和 Debian archive 均通过，整轮为 15/17。Ubuntu 两格容器因最小镜像的 /usr/share/doc 安装过滤，无法读取包内文档而 FAIL；Debian 容器通过。

修正仅在测试 Dockerfile 的本地 apt install 明确加入 dpkg --path-include=/usr/share/doc/webpatch/*，使夹具能验证包的已安装文档字节。不修改产品安装策略或宿主环境，不取消文档断言。

Validation: 617 local tests PASS; raw failed logs and source/JUnit hashes retained. Native Ubuntu container documentation inclusion CI_PENDING. Actual public CLI source remains ba5d9f6 and its eight service cases passed; final matrix still required.
