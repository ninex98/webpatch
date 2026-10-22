# FPM 测试 pool 访问与错误码 / FPM fixture access and error codes

2ef6b0b 的 noble/fpm：真实执行输入审计 PASS；受控 unit 加载与服务重启完成，但显式 warm-up 探针触发 PARTIAL。原始审计、服务日志和签名 recovery 结果附后；不会把重启成功标为准备通过。

新增 pool 的配置没有 listen.owner/listen.group，未给 www-data nginx 提供 socket 访问权限。测试配置显式设置两项为 www-data；生产配置不被自动修改。prepare-scope 现在保存受限格式的 PROBE/KERNEL 错误码，任意异常文本仍隐藏，便于核实真实失败原因。

本地 502 tests PASS，含错误码保留和私有异常正文隐藏反例；bash -n PASS。真实四格受控启动及当前收据复核 CI pending。
