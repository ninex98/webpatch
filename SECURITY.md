# Security model

WebPatch is a defensive, read-only preview. It does not exploit CVEs or prove that a machine is uncompromised. Local metadata and process observations are untrusted evidence. Phase one never emits a verified-safe runtime verdict and ships no write-capable executor.

Report suspected false-safe decisions, unintended writes, unsafe command execution, or rule/source confusion privately to the repository maintainer through the hosting platform's private security advisory feature when this project is published. No reporting email or hosted repository has been configured yet; do not submit secrets in public issues.

Changes to bundled rules require official vendor references, review timestamps, finite validity, boundary tests and re-running integration checks. Third-party versions must not inherit a distribution's safe verdict merely because their version sorts higher.
