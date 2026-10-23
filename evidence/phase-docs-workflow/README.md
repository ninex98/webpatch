# 操作说明与包内文档 / Workflow and packaged documentation

范围 / Scope: align bilingual capability matrices, distinguish diagnostic schema 4 from managed schema 5, document receipt extraction/hash confirmation, blocked/partial/manual recovery semantics, and independently scoped extensions. Preserve the existing visual assets. Update .deb description and include CLI/phase-three/phase-four documents.

PASS: 605 local tests, current CLI help for eight workflow commands, changed-document local links, Python compile and source/docs diff check. Logs/JUnit and source hashes are retained. This validation does not execute the documented commands against the developer host.

CI_PENDING: native package build/install including the added documents. Public package apply remains disabled; latest full native repair matrix is still pending. The documentation states that boundary explicitly.
