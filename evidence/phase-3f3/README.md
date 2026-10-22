# 3F.3 当前消费者与证据时效 / Current consumers and evidence validity

本地 547 tests PASS。新增未映射/硬链接文件持有者、描述符不可读/变化、磁盘字节变化、采集期间过期、持锁复核后过期、完整源代码/规则绑定及注入子类不得获得宿主变更能力的反例。

CI pending：三个只读容器验证真实描述符读取；四格 VM 验证 mmap、仅 open 及线程独立 FD 表的未知持有者均阻断。线程实验只在临时 helper 中 unshare 文件表，既不创建 namespace，也不运行目标 PHP 字节。原有受控启动和当前计划检查继续运行。

当前证据不宣称全局安全、任意未来程序或匿名内存完整性。公共 apply 仍禁用。源码/日志/JUnit/制品摘要见本目录。
