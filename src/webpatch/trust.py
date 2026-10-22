"""Offline Ubuntu archive authentication using existing signed APT lists.

No refresh, downloads, installation, or historical-origin inference. Missing
cached archives keep installed runtime identity UNKNOWN.
"""

from datetime import timedelta
from email.utils import parsedate_to_datetime
import hashlib
import json
import re
from urllib.parse import urlsplit

from .sources import KEYRING, official_source, paragraphs


UBUNTU_SIGNER = "F6ECB3762474EDA9D21B7022871920D1991BC93C"
LISTS = "/var/lib/apt/lists"
SHA256 = re.compile(r"[a-f0-9]{64}\Z")


def signature_command(path):
    return ("/usr/bin/gpgv", "--status-fd=1", "--keyring", KEYRING, path)


def release_payload(raw):
    if not raw.startswith("-----BEGIN PGP SIGNED MESSAGE-----\n") or raw.count("-----BEGIN PGP SIGNATURE-----") != 1:
        raise ValueError("INVALID_CLEARSIGNED_RELEASE")
    payload = raw.split("\n\n", 1)[1].split("-----BEGIN PGP SIGNATURE-----", 1)[0]
    payload = "\n".join(line[2:] if line.startswith("- ") else line for line in payload.splitlines())
    rows = paragraphs(payload)
    if len(rows) != 1:
        raise ValueError("INVALID_RELEASE_FIELDS")
    return rows[0]


def verified_release(raw, result, suite, codename, now):
    if result is None or result.returncode:
        raise ValueError("RELEASE_SIGNATURE_FAILED")
    statuses = result.stdout.splitlines()
    if any(re.search(r"\b(?:BADSIG|ERRSIG|EXPKEYSIG|EXPSIG|REVKEYSIG|NO_PUBKEY)\b", line) for line in statuses):
        raise ValueError("RELEASE_SIGNATURE_FAILED")
    if not any(line.startswith("[GNUPG:] VALIDSIG " + UBUNTU_SIGNER + " ") for line in statuses):
        raise ValueError("RELEASE_SIGNER_NOT_PINNED")
    release = release_payload(raw)
    if release.get("Origin") != "Ubuntu" or release.get("Label") != "Ubuntu" or release.get("Suite") != suite or release.get("Codename") != codename:
        raise ValueError("SIGNED_RELEASE_SCOPE_MISMATCH")
    date = parsedate_to_datetime(release["Date"])
    if not date.tzinfo or date > now + timedelta(minutes=5):
        raise ValueError("RELEASE_DATE_INVALID")
    # Base pockets are immutable release snapshots, never fresh repair candidates.
    if suite != codename and now - date > timedelta(days=7):
        raise ValueError("RELEASE_TOO_OLD")
    if "Valid-Until" in release:
        expiry = parsedate_to_datetime(release["Valid-Until"])
        if not expiry.tzinfo or now >= expiry or expiry <= date:
            raise ValueError("RELEASE_EXPIRED")
    entries = {}
    for line in release.get("SHA256", "").splitlines():
        fields = line.split()
        if not fields: continue
        if len(fields) != 3 or not SHA256.fullmatch(fields[0]) or not fields[1].isdigit() or fields[2] in entries:
            raise ValueError("RELEASE_HASH_TABLE_INVALID")
        entries[fields[2]] = (fields[0], int(fields[1]))
    if not entries:
        raise ValueError("RELEASE_HASH_TABLE_MISSING")
    return entries


def source_identity(record):
    value = record.get("Source", record.get("Package", ""))
    match = re.fullmatch(r"([a-z0-9][a-z0-9+.-]*)(?: \(([^()\s]+)\))?", value)
    if not match:
        raise ValueError("SOURCE_IDENTITY_MALFORMED")
    return match[1], match[2] or record["Version"]


def authenticate(collector, inventory, sources, now, package_cache="/var/cache/apt/archives"):
    start = len(collector.evidence)
    blockers, candidates, installed = [], [], []
    def probe(operation, path):
        return collector.probe(operation, path)[0]
    if inventory.environment.os_id != "ubuntu" or inventory.environment.codename not in {"jammy", "noble"}:
        return {"status": "UNKNOWN", "blockers": ["ARCHIVE_AUTHENTICATION_UNSUPPORTED_RELEASE"], "candidates": [], "installed": [], "evidence_ids": []}
    if not inventory.packages:
        return {"status": "UNKNOWN", "blockers": ["NO_PACKAGES_TO_AUTHENTICATE"], "candidates": [], "installed": [], "evidence_ids": []}
    names = probe("listdir", LISTS)
    if names is None:
        names = []
        blockers.append("APT_LISTS_UNREADABLE")
    architectures = {p.architecture for p in inventory.packages if re.fullmatch(r"[a-z0-9-]+", p.architecture)}
    seen = set()
    for source in sources.sources:
        try:
            if not official_source(source, inventory.environment.codename): continue
        except ValueError:
            continue
        url = urlsplit(source.uri)
        prefix = (url.netloc + url.path.rstrip("/")).replace("/", "_") + "_dists_" + source.suite
        release_path = LISTS + "/" + prefix + "_InRelease"
        if release_path in seen: continue
        seen.add(release_path)
        raw = probe("read_text", release_path)
        if raw is None:
            blockers.append("SIGNED_RELEASE_UNAVAILABLE:" + source.suite)
            continue
        signature = probe("run", signature_command(release_path))
        if probe("read_text", release_path) != raw:
            blockers.append("RELEASE_CHANGED_DURING_VERIFICATION")
            continue
        try:
            entries = verified_release(raw, signature, source.suite, inventory.environment.codename, now)
        except (ValueError, KeyError, IndexError, TypeError):
            blockers.append("RELEASE_AUTHENTICATION_OR_FRESHNESS_FAILED:" + source.suite)
            continue
        release_hash = hashlib.sha256(raw.encode()).hexdigest()
        # Sources for the same suite may list different components in separate stanzas.
        components = set(c for s in sources.sources if s.uri == source.uri and s.suite == source.suite for c in s.components)
        for component in sorted(components):
            for architecture in sorted(architectures):
                if architecture == "all": continue
                relative = f"{component}/binary-{architecture}/Packages"
                basename = prefix + "_" + relative.replace("/", "_")
                matches = [n for n in names if n in {basename, basename + ".lz4", basename + ".gz", basename + ".xz"}]
                if len(matches) != 1 or relative not in entries:
                    blockers.append("INDEX_MISSING_OR_AMBIGUOUS:" + source.suite + ":" + relative)
                    continue
                index = probe("package_index", LISTS + "/" + matches[0])
                if index is None or (index.get("sha256"), index.get("size")) != entries[relative]:
                    blockers.append("INDEX_SHA256_OR_SIZE_MISMATCH:" + relative)
                    continue
                for record in index["packages"]:
                    try:
                        name, version, arch = (record[k] for k in ("Package", "Version", "Architecture"))
                        if arch not in {architecture, "all"} or not SHA256.fullmatch(record["SHA256"]) or not record["Size"].isdigit():
                            raise ValueError("INVALID_PACKAGE_RECORD")
                        source_name, source_version = source_identity(record)
                        if not re.fullmatch(r"[a-z0-9][a-z0-9+.-]+", name) or not record["Filename"].startswith("pool/") or ".." in record["Filename"].split("/"):
                            raise ValueError("INVALID_PACKAGE_RECORD")
                        candidates.append({"name": name, "version": version, "architecture": arch,
                                           "source_name": source_name, "source_version": source_version,
                                           "sha256": record["SHA256"], "size": int(record["Size"]),
                                           "filename": record["Filename"], "suite": source.suite,
                                           "fresh_for_plan": source.suite != inventory.environment.codename,
                                           "release_sha256": release_hash, "index_sha256": index["sha256"],
                                           "signer": UBUNTU_SIGNER})
                    except (KeyError, ValueError):
                        blockers.append("AUTHENTICATED_INDEX_RECORD_MALFORMED")
    if not candidates:
        blockers.append("NO_AUTHENTICATED_PACKAGE_CANDIDATES")
    archive_names = probe("listdir", package_cache)
    chain_evidence_ids = [e.id for e in collector.evidence[start:]]
    for package in inventory.packages:
        package_evidence_start = len(collector.evidence)
        if package.sapi not in {"fpm", "apache2", "cli", "cgi", "component_or_unknown"}: continue
        matching = [c for c in candidates if (c["name"], c["version"], c["architecture"], c["source_name"], c["source_version"])
                    == (package.name.split(":")[0], package.version, package.architecture, package.source_name, package.source_version)]
        hashes = {c["sha256"] for c in matching}
        reasons = []
        verified_files = {}
        archive_hash = None
        if len(hashes) != 1:
            reasons.append("INSTALLED_VERSION_NOT_UNIQUELY_AUTHENTICATED")
        else:
            candidate = matching[0]
            paths = [package_cache.rstrip("/") + "/" + n for n in archive_names or []
                     if n.startswith(candidate["name"] + "_") and n.endswith(".deb")]
            for path in paths[:32]:
                fingerprint = probe("fingerprint", path)
                if not fingerprint or (fingerprint["sha256"], fingerprint["size"]) != (candidate["sha256"], candidate["size"]):
                    continue
                archive = probe("package_archive", path)
                if archive is None or probe("fingerprint", path) != fingerprint:
                    reasons.append("ARCHIVE_CHANGED_OR_UNREADABLE")
                    continue
                control = archive["control"]
                try:
                    identity = (control["Package"], control["Version"], control["Architecture"], *source_identity(control))
                    if identity != (candidate["name"], candidate["version"], candidate["architecture"], candidate["source_name"], candidate["source_version"]):
                        raise ValueError("CONTROL_IDENTITY_MISMATCH")
                except (KeyError, ValueError):
                    reasons.append("ARCHIVE_CONTROL_IDENTITY_MISMATCH")
                    continue
                archive_hash = fingerprint["sha256"]
                for filename, expected in archive["files"].items():
                    actual = probe("fingerprint", filename)
                    if actual is None or actual["sha256"] != expected:
                        reasons.append("INSTALLED_RUNTIME_FILE_MISMATCH_OR_UNREADABLE")
                    else:
                        verified_files[filename] = expected
                break
            if archive_hash is None:
                reasons.append("AUTHENTICATED_CACHED_DEB_UNAVAILABLE")
            elif not verified_files:
                reasons.append("NO_AUTHENTICATED_RUNTIME_FILES")
        installed.append({"package_id": package.id, "status": "AUTHENTICATED_RUNTIME_FILES" if not reasons else "UNKNOWN",
                          "archive_sha256": archive_hash, "files": verified_files, "blockers": sorted(set(reasons)),
                          "evidence_ids": [package.evidence_id, *chain_evidence_ids,
                                           *[e.id for e in collector.evidence[package_evidence_start:]]]})
    inputs = [(e.operation, e.target, e.outcome, e.sha256) for e in collector.evidence[start:]]
    return {"status": "VERIFIED_INDEX_CHAIN" if candidates and not blockers else "UNKNOWN",
            "blockers": sorted(set(blockers)), "candidates": candidates, "installed": installed,
            "sha256": hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest(),
            "evidence_ids": [e.id for e in collector.evidence[start:]]}
