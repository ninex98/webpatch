from datetime import datetime
import json
from pathlib import Path

import pytest

from webpatch.system import CommandResult, DPKG_QUERY, ProbeError


FIXTURES = Path(__file__).parent / "fixtures"
CASES = json.loads((FIXTURES / "environments.json").read_text())
COMPARISONS = json.loads((FIXTURES / "comparisons.json").read_text())
NOW = datetime.fromisoformat("2026-10-22T08:00:00+00:00")


class FakeSystem:
    """Every operation must be in the explicit fixture; no local fallback."""

    def __init__(self, case):
        self.calls = []
        vendor, version, codename = case.get("os", ["ubuntu", "22.04", "jammy"])
        missing = ProbeError("FileNotFoundError")
        self.reads = {
            "/etc/os-release": (missing if case.get("missing_os") else
                                f'ID={vendor}\nVERSION_ID="{version}"\nVERSION_CODENAME={codename}\n'),
            "/.dockerenv": "" if case.get("docker") else missing,
            "/run/.containerenv": "" if case.get("podman") else missing,
            "/proc/self/cgroup": case.get("cgroup", "0::/user.slice"),
        }
        self.links = {"/proc/self/ns/mnt": "mnt:[1]"}
        self.links["/proc/self/ns/pid"] = "pid:[1]"
        self.identities = {"/": {"device": 1, "inode": 1}}
        self.fingerprints = {}
        self.reads.update({p: missing for p in ("/etc/nginx/nginx.conf", "/etc/apache2/apache2.conf")})
        self.dirs = {p: missing for p in (
            "/etc/php", "/www/server/php", "/opt/php", "/usr/local/bin", "/usr/local/sbin")}
        self.dirs.update({"/run": [], "/run/containerd": missing, "/proc": []})
        self.reads.update({p: missing for p in ("/etc/apt/sources.list", "/etc/apt/preferences", "/etc/apt/apt.conf")})
        self.dirs.update({p: [] for p in ("/etc/apt/sources.list.d", "/etc/apt/preferences.d", "/etc/apt/apt.conf.d")})
        self.dirs.update(case.get("directories", {}))
        self.dirs.update({p: ProbeError(e) for p, e in case.get("directory_errors", {}).items()})
        for proc in case.get("processes", []):
            pid = str(proc["pid"])
            self.dirs["/proc"].append(pid)
            self.reads[f"/proc/{pid}/comm"] = (ProbeError(proc["comm_error"]) if "comm_error" in proc
                                               else proc["comm"])
            self.links[f"/proc/{pid}/exe"] = (ProbeError(proc["exe_error"]) if "exe_error" in proc
                                              else proc.get("exe", "/unknown"))
            self.links[f"/proc/{pid}/ns/mnt"] = (ProbeError(proc["ns_error"]) if "ns_error" in proc
                                                 else proc.get("ns", "mnt:[1]"))
            self.links[f"/proc/{pid}/ns/pid"] = missing
            self.reads[f"/proc/{pid}/stat"] = missing
            self.identities[f"/proc/{pid}/root"] = missing
        if "proc_error" in case:
            self.dirs["/proc"] = ProbeError(case["proc_error"])
        raw = case.get("raw_packages", "".join("\t".join(row) + "\n" for row in case.get("packages", [])))
        self.commands = {DPKG_QUERY: (ProbeError(case["query_error"]) if "query_error" in case
                                     else CommandResult(case.get("query_rc", 0), raw, case.get("query_stderr", "")))}
        import re
        for row in case.get("packages", []):
            if re.fullmatch(r"php[0-9]+\.[0-9]+", row[3]) and row[0].split(":")[0].endswith("-fpm"):
                root = f"/etc/php/{row[3][3:]}/fpm"
                self.reads[root + "/php-fpm.conf"] = missing
                self.reads[root + "/php.ini"] = missing
                self.dirs[root + "/conf.d"] = missing
        for installed, fixed, meets in COMPARISONS:
            self.commands[("/usr/bin/dpkg", "--compare-versions", installed, "ge", fixed)] = (
                CommandResult(2, "", "invalid") if case.get("compare_error") else CommandResult(0 if meets else 1))

    def _get(self, operation, mapping, key):
        self.calls.append((operation, key))
        assert key in mapping, f"Undeclared fixture I/O: {operation} {key}"
        result = mapping[key]
        if isinstance(result, Exception):
            raise result
        return result

    def read_text(self, path):
        return self._get("read_text", self.reads, path)

    def readlink(self, path):
        return self._get("readlink", self.links, path)

    def listdir(self, path):
        return self._get("listdir", self.dirs, path)

    def run(self, argv):
        return self._get("run", self.commands, argv)

    def identity(self, path):
        return self._get("identity", self.identities, path)

    def fingerprint(self, path):
        return self._get("fingerprint", self.fingerprints, path)


@pytest.fixture(params=CASES, ids=lambda c: c["id"])
def server(request, monkeypatch):
    # Accidental production command execution in fixture tests must fail loudly.
    def forbidden(*args, **kwargs):
        raise AssertionError("Fixture test attempted to execute a host command")
    monkeypatch.setattr("subprocess.Popen", forbidden)
    return request.param, FakeSystem(request.param)
