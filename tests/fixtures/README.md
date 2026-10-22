# Fixture provenance

`environments.json` contains synthetic server observations, not captures from the developer's host and not exploit environments. Package lines follow the documented dpkg-query format. Fixed boundaries were independently reviewed against the official sources in `docs/design.md` on 2026-10-22.

`comparisons.json` records explicit expected Debian ordering results. The fake reader uses these exact pairs without implementing an ordering algorithm. Docker integration runs every pair against real dpkg. Adding an unrecorded command/read fails tests; fake reads never fall back to local OS access.

These fixtures test decision semantics and coverage gaps, not cryptographic package provenance, full runtime discovery or actual remediation. Each case includes its expected outcome; malformed and permission scenarios deliberately preserve uncertainty.
