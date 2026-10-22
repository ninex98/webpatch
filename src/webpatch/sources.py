"""APT configuration audit. Source names are policy inputs, not trust roots."""

from dataclasses import dataclass
import hashlib
import json
import re
import shlex
from urllib.parse import urlsplit

from .system import DPKG_QUERY
from .archive_policy import UBUNTU_KEYRING,DEBIAN_KEYRING,archive_keyring,archive_keyrings,supported_archive


KEYRING = UBUNTU_KEYRING


@dataclass(frozen=True)
class Source:
    uri: str
    suite: str
    components: tuple[str, ...]
    signed_by: str
    path: str


@dataclass(frozen=True)
class SourceAudit:
    status: str
    sources: tuple[Source, ...]
    blockers: tuple[str, ...]
    sha256: str
    evidence_ids: tuple[str, ...]


def paragraphs(raw):
    """Strict deb822 with continuations and duplicate-field rejection."""
    rows, row, key = [], {}, None
    for line in raw.splitlines() + [""]:
        if not line.strip():
            if row: rows.append(row)
            row, key = {}, None
        elif line.startswith("#"):
            continue
        elif line[0].isspace() and key:
            row[key] += "\n" + line[1:]
        elif ":" in line and not line[0].isspace():
            key, value = line.split(":", 1)
            if key in row or not re.fullmatch(r"[A-Za-z0-9-]+", key):
                raise ValueError("AMBIGUOUS_DEB822")
            row[key] = value.strip()
        else:
            raise ValueError("MALFORMED_DEB822")
    return rows


def parse_sources(raw, path, default_keyring=KEYRING):
    rows = []
    if path.endswith(".sources"):
        for row in paragraphs(raw):
            if row.get("Enabled", "yes") == "no":
                continue
            allowed = {"Types", "URIs", "Suites", "Components", "Signed-By", "Architectures", "Enabled"}
            if set(row) - allowed or row.get("Types") not in {"deb", "deb deb-src"}:
                raise ValueError("UNSUPPORTED_SOURCE_OPTIONS")
            for uri in row.get("URIs", "").split():
                for suite in row.get("Suites", "").split():
                    rows.append(Source(uri, suite, tuple(row.get("Components", "").split()), row.get("Signed-By", default_keyring), path))
            if not row.get("URIs") or not row.get("Suites"):
                raise ValueError("EMPTY_SOURCE_FIELDS")
    else:
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = re.fullmatch(r"(deb|deb-src)\s+(?:\[([^\]]+)\]\s+)?([^\s]+)\s+([^\s]+)\s+(.+?)(?:\s+#.*)?", line)
            if not match:
                raise ValueError("MALFORMED_SOURCES_LIST")
            if match[1] == "deb-src":
                continue
            options = {}
            for option in shlex.split(match[2] or ""):
                if "=" not in option:
                    raise ValueError("MALFORMED_SOURCE_OPTIONS")
                key, value = option.split("=", 1)
                if key in options or key not in {"signed-by", "arch"}:
                    raise ValueError("UNSUPPORTED_SOURCE_OPTIONS")
                options[key] = value
            rows.append(Source(match[3], match[4], tuple(match[5].split()), options.get("signed-by", default_keyring), path))
    return rows


def official_source(source, codename, os_id='ubuntu'):
    url = urlsplit(source.uri)
    host = url.hostname or ""
    if os_id=='debian':
        security=source.suite==codename+'-security'
        official=(host in {'deb.debian.org','security.debian.org'} and url.path.rstrip('/')=='/debian-security') if security else (
            host in {'deb.debian.org','ftp.debian.org'} and url.path.rstrip('/')=='/debian')
        return (supported_archive(os_id,codename) and official and url.scheme in {'http','https'}
                and not url.username and not url.password and not url.query and not url.fragment and url.port is None
                and source.suite in {codename,codename+'-security',codename+'-updates'}
                and bool(source.components) and set(source.components)<={'main'} and source.signed_by in archive_keyrings('debian'))
    if os_id!='ubuntu': return False
    official = host in {"archive.ubuntu.com", "security.ubuntu.com", "ports.ubuntu.com"} or host.endswith(".archive.ubuntu.com")
    return (official and url.scheme in {"http", "https"} and not url.username and not url.password
            and not url.query and not url.fragment and url.port is None
            and url.path.rstrip("/") in {"/ubuntu", "/ubuntu-ports"}
            and source.suite in {codename, codename + "-security", codename + "-updates"}
            and bool(source.components) and set(source.components) <= {"main", "restricted", "universe", "multiverse"}
            and source.signed_by == KEYRING)


def audit_sources(collector, inventory):
    start = len(collector.evidence)
    blockers, sources, inputs = [], [], []
    def read(path, optional=False):
        raw, _ = collector.probe("read_text", path)
        inputs.append((path, collector.evidence[-1].outcome, collector.evidence[-1].sha256))
        if raw is None and (not optional or collector.evidence[-1].outcome != "FileNotFoundError"):
            blockers.append("APT_INPUT_UNREADABLE:" + path)
        return raw
    def directory(path):
        names, _ = collector.probe("listdir", path)
        inputs.append((path, collector.evidence[-1].outcome, collector.evidence[-1].sha256))
        if names is None:
            blockers.append("APT_DIRECTORY_UNREADABLE:" + path)
        return names or []
    paths = ["/etc/apt/sources.list"]
    paths += ["/etc/apt/sources.list.d/" + n for n in directory("/etc/apt/sources.list.d") if n.endswith((".list", ".sources"))]
    for path in paths:
        raw = read(path, optional=path == "/etc/apt/sources.list")
        if raw is None: continue
        try:
            sources.extend(parse_sources(raw, path,archive_keyring(inventory.environment.os_id)))
        except ValueError as exc:
            blockers.append(str(exc) + ":" + path)
    if not supported_archive(inventory.environment.os_id,inventory.environment.codename):
        blockers.append("SOURCE_POLICY_UNSUPPORTED_RELEASE")
    for source in sources:
        try:
            valid = official_source(source, inventory.environment.codename,inventory.environment.os_id)
        except ValueError:
            valid = False
        if not valid:
            blockers.append("THIRD_PARTY_MIXED_RELEASE_OR_KEY_SCOPE:" + source.path)
    if not sources:
        blockers.append("NO_ACTIVE_BINARY_SOURCES")
    elif not any(s.suite == inventory.environment.codename + "-security" for s in sources):
        blockers.append("SECURITY_POCKET_MISSING")
    configs = ["/etc/apt/preferences", "/etc/apt/apt.conf"]
    for folder in ("/etc/apt/preferences.d", "/etc/apt/apt.conf.d"):
        configs += [folder + "/" + name for name in directory(folder) if re.fullmatch(r"[A-Za-z0-9_-]+(?:\.conf)?", name)]
    for path in configs:
        raw = read(path, optional=path in {"/etc/apt/preferences", "/etc/apt/apt.conf"})
        if not raw: continue
        content = "\n".join(line for line in raw.splitlines() if not line.lstrip().startswith(("//", "#")))
        if "/preferences" in path and content.strip():
            blockers.append("APT_PIN_REQUIRES_REVIEW")
        if re.search(r"(?:Pre|Post)-Invoke|Pre-Install-Pkgs", raw, re.I):
            blockers.append("APT_HOOKS_REQUIRE_REVIEW")
        if re.search(r"#(?:include|clear)|Dir::|AllowUnauthenticated|AllowInsecure|Check-Valid-Until|Check-Date|Default-Release|DPkg::Options|APT::Architecture", raw, re.I):
            blockers.append("APT_CONFIGURATION_OVERRIDE_REQUIRES_REVIEW")
    for path in ("/var/lib/apt/extended_states", "/var/lib/dpkg/arch", "/var/lib/dpkg/diversions", "/var/lib/dpkg/statoverride"):
        raw = read(path, optional=True)
        if raw and path.endswith("/diversions"):
            blockers.append("DPKG_DIVERSIONS_REQUIRE_REVIEW")
    if directory("/var/lib/dpkg/updates"):
        blockers.append("DPKG_PENDING_UPDATES")
    packages, _ = collector.probe("run", DPKG_QUERY)
    inputs.append(("dpkg", collector.evidence[-1].outcome, collector.evidence[-1].sha256))
    if packages is None or packages.returncode or packages.stderr:
        blockers.append("DPKG_STATE_UNREADABLE")
    else:
        for line in packages.stdout.splitlines():
            fields = line.split("\t")
            if len(fields) != 6:
                blockers.append("DPKG_STATE_MALFORMED")
            elif fields[5].startswith("hold "):
                blockers.append("HELD_PACKAGES_REQUIRE_REVIEW")
            elif fields[5] not in {"install ok installed", "deinstall ok config-files", "purge ok not-installed", "unknown ok not-installed"}:
                blockers.append("DPKG_UNCONFIGURED_OR_ABNORMAL_STATE")
    # URI credentials are excluded from the serialized model, including unsupported sources.
    def redact(uri):
        try:
            url = urlsplit(uri)
            return uri if not (url.username or url.password or url.query or url.fragment) else "REDACTED_CREDENTIAL_URI"
        except ValueError:
            return "INVALID_URI"
    public = tuple(Source(redact(s.uri), s.suite, s.components, s.signed_by, s.path) for s in sources)
    digest = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    return SourceAudit("POLICY_CHECKED_NOT_AUTHENTICATED" if not blockers else "UNKNOWN",
                       public, tuple(sorted(set(blockers))), digest,
                       tuple(e.id for e in collector.evidence[start:]))
