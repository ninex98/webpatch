"""The only production OS boundary; there is deliberately no write interface."""

import hashlib
import io
import json
import os
from pathlib import Path
import re
import selectors
import stat
import subprocess
import tarfile
import time
from dataclasses import dataclass
from typing import Protocol

from .models import Evidence


DPKG_QUERY = (
    "/usr/bin/dpkg-query", "-W",
    "-f=${binary:Package}\t${Version}\t${Architecture}\t${source:Package}"
    "\t${source:Version}\t${Status}\n",
)
VERSION = re.compile(r"[0-9][A-Za-z0-9.+:~\-]{0,255}\Z")
MAX_FILE_BYTES = 1024 * 1024
MAX_COMMAND_BYTES = 8 * 1024 * 1024
MAX_DIRECTORY_ENTRIES = 16384
COMMAND_TIMEOUT_SECONDS = 10


class ProbeError(Exception):
    """A failed read is evidence of missing coverage, never an empty success."""


class PolicyError(ProbeError):
    pass


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class SystemReader(Protocol):
    def run(self, argv: tuple[str, ...]) -> CommandResult: ...
    def read_text(self, path: str) -> str: ...
    def listdir(self, path: str) -> list[str]: ...
    def readlink(self, path: str) -> str: ...
    def fingerprint(self, path: str) -> dict: ...
    def identity(self, path: str) -> dict: ...
    def package_index(self, path: str) -> dict: ...
    def package_archive(self, path: str) -> dict: ...


SERVICE_PROPERTIES = "Id,LoadState,ActiveState,SubState,MainPID,ControlGroup,FragmentPath"
SAFE_PATH = re.compile(r"/(?:[A-Za-z0-9_.+@-]+/)*[A-Za-z0-9_.+@-]+\Z")


def service_command(unit: str) -> tuple[str, ...]:
    return ("/usr/bin/systemctl", "show", "--no-pager", f"--property={SERVICE_PROPERTIES}", unit)


def validate_command(argv: tuple[str, ...]) -> None:
    if argv == DPKG_QUERY:
        return
    if (len(argv) == 5 and argv[:4] == ("/usr/bin/gpgv", "--status-fd=1", "--keyring", "/usr/share/keyrings/ubuntu-archive-keyring.gpg")
            and re.fullmatch(r"/var/lib/apt/lists/[A-Za-z0-9_.%+-]+_InRelease", argv[4])):
        return
    if (len(argv) == 3 and argv[:2] == ("/usr/lib/apt/apt-helper", "cat-file")
            and re.fullmatch(r"/var/lib/apt/lists/[A-Za-z0-9_.%+-]+_Packages(?:\.lz4|\.gz|\.xz)?", argv[2])):
        return
    if (len(argv) == 3 and argv[0] == "/usr/bin/dpkg-deb" and argv[1] in {"--ctrl-tarfile", "--fsys-tarfile"}
            and SAFE_PATH.fullmatch(argv[2]) and ".." not in argv[2].split("/") and argv[2].endswith(".deb")):
        return
    if (len(argv) == 3 and argv[:2] == ("/usr/bin/dpkg-query", "-S")
            and SAFE_PATH.fullmatch(argv[2]) and ".." not in argv[2].split("/")):
        return
    if (len(argv) == 5 and argv == service_command(argv[-1])
            and re.fullmatch(r"(?:php[0-9]+\.[0-9]+-fpm|apache2|nginx)\.service", argv[-1])):
        return
    if (len(argv) == 5 and argv[:2] == ("/usr/bin/dpkg", "--compare-versions")
            and argv[3] == "ge" and VERSION.fullmatch(argv[2])
            and VERSION.fullmatch(argv[4])):
        return
    raise PolicyError("COMMAND_NOT_ALLOWLISTED")


class LocalSystem:
    """Bounded reads and fixed argv, no shell, network or inherited command config."""

    def run(self, argv: tuple[str, ...]) -> CommandResult:
        try:
            code, stdout, stderr = self._execute(argv)
            return CommandResult(code, stdout.decode("utf-8", "strict"), stderr.decode("utf-8", "strict"))
        except UnicodeError as exc:
            raise ProbeError(type(exc).__name__) from exc

    def _execute(self, argv, limit=None):
        limit = MAX_COMMAND_BYTES if limit is None else limit
        validate_command(argv)
        env = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C",
               "LANG": "C", "DPKG_PAGER": "/bin/cat", "DPKG_COLORS": "never"}
        try:
            with subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, env=env, cwd="/", shell=False) as proc:
                buffers = [bytearray(), bytearray()]
                deadline = time.monotonic() + COMMAND_TIMEOUT_SECONDS
                try:
                    with selectors.DefaultSelector() as selector:
                        selector.register(proc.stdout, selectors.EVENT_READ, 0)
                        selector.register(proc.stderr, selectors.EVENT_READ, 1)
                        while selector.get_map():
                            remaining = deadline - time.monotonic()
                            if remaining <= 0:
                                raise ProbeError("COMMAND_TIMEOUT")
                            for key, _ in selector.select(min(remaining, 0.1)):
                                chunk = os.read(key.fileobj.fileno(), 65536)
                                if not chunk:
                                    selector.unregister(key.fileobj)
                                    continue
                                buffers[key.data].extend(chunk)
                                if sum(map(len, buffers)) > limit:
                                    raise ProbeError("COMMAND_OUTPUT_LIMIT")
                    proc.wait(timeout=max(0.001, deadline - time.monotonic()))
                except BaseException:
                    proc.kill()
                    proc.wait()
                    raise
                return proc.returncode, *(bytes(b) for b in buffers)
        except (OSError, UnicodeError, subprocess.TimeoutExpired) as exc:
            raise ProbeError(type(exc).__name__) from exc

    def read_text(self, path: str) -> str:
        try:
            with os.fdopen(os.open(path, os.O_RDONLY | os.O_NONBLOCK), "rb") as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise ProbeError("FILE_TYPE_LIMIT")
                content = stream.read(MAX_FILE_BYTES + 1)
            if len(content) > MAX_FILE_BYTES:
                raise ProbeError("FILE_SIZE_LIMIT")
            return content.decode("utf-8", "strict")
        except (OSError, UnicodeError) as exc:
            raise ProbeError(type(exc).__name__) from exc

    def listdir(self, path: str) -> list[str]:
        try:
            result = []
            with os.scandir(path) as entries:
                for entry in entries:
                    result.append(entry.name)
                    if len(result) > MAX_DIRECTORY_ENTRIES:
                        raise ProbeError("DIRECTORY_ENTRY_LIMIT")
            return sorted(result)
        except OSError as exc:
            raise ProbeError(type(exc).__name__) from exc

    def readlink(self, path: str) -> str:
        try:
            return os.readlink(path)
        except OSError as exc:
            raise ProbeError(type(exc).__name__) from exc

    def identity(self, path: str) -> dict:
        try:
            info = os.stat(path)
            return {"device": info.st_dev, "inode": info.st_ino}
        except OSError as exc:
            raise ProbeError(type(exc).__name__) from exc

    def package_index(self, path: str) -> dict:
        from .sources import paragraphs
        code, raw, stderr = self._execute(("/usr/lib/apt/apt-helper", "cat-file", path), 256 * 1024 * 1024)
        if code or stderr:
            raise ProbeError("INDEX_DECOMPRESSION_FAILED")
        try:
            rows = []
            for paragraph in raw.decode("utf-8").split("\n\n"):
                if re.match(r"Package: (?:php|libapache2-mod-php|libphp)", paragraph):
                    rows.extend(paragraphs(paragraph))
            return {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw), "packages": rows}
        except (ValueError, UnicodeError) as exc:
            raise ProbeError("INDEX_MALFORMED") from exc

    def package_archive(self, path: str) -> dict:
        from .sources import paragraphs
        result = {"files": {}}
        try:
            for option in ("--ctrl-tarfile", "--fsys-tarfile"):
                code, raw, stderr = self._execute(("/usr/bin/dpkg-deb", option, path), 256 * 1024 * 1024)
                if code or stderr:
                    raise ProbeError("PACKAGE_ARCHIVE_READ_FAILED")
                with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
                    seen = set()
                    for member in archive:
                        name = member.name.removeprefix("./")
                        if name in seen or name.startswith("/") or ".." in name.split("/") or len(seen) > 16384:
                            raise ProbeError("PACKAGE_ARCHIVE_PATH_INVALID")
                        seen.add(name)
                        if member.isfile():
                            stream = archive.extractfile(member)
                            if option == "--ctrl-tarfile" and name == "control":
                                result["control"] = paragraphs(stream.read().decode("utf-8"))[0]
                            elif option == "--fsys-tarfile" and name.startswith(("usr/bin/", "usr/sbin/", "usr/lib/")):
                                result["files"]["/" + name] = hashlib.sha256(stream.read()).hexdigest()
            if "control" not in result or not result["files"]:
                raise ProbeError("PACKAGE_RUNTIME_FILES_MISSING")
            return result
        except (tarfile.TarError, ValueError, UnicodeError, IndexError) as exc:
            raise ProbeError("PACKAGE_ARCHIVE_MALFORMED") from exc

    def fingerprint(self, path: str) -> dict:
        """Hash an already-open regular file; reject replacement during reading."""
        try:
            with os.fdopen(os.open(path, os.O_RDONLY | os.O_NONBLOCK), "rb") as stream:
                before = os.fstat(stream.fileno())
                if not stat.S_ISREG(before.st_mode) or before.st_size > 256 * 1024 * 1024:
                    raise ProbeError("FILE_TYPE_OR_SIZE_LIMIT")
                digest = hashlib.sha256()
                total = 0
                while chunk := stream.read(1024 * 1024):
                    total += len(chunk)
                    if total > 256 * 1024 * 1024:
                        raise ProbeError("FILE_SIZE_LIMIT")
                    digest.update(chunk)
                after = os.fstat(stream.fileno())
                fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
                if any(getattr(before, f) != getattr(after, f) for f in fields):
                    raise ProbeError("FILE_CHANGED_DURING_READ")
                return {"device": after.st_dev, "inode": after.st_ino,
                        "size": after.st_size, "sha256": digest.hexdigest(),
                        "mtime_ns": after.st_mtime_ns, "ctime_ns": after.st_ctime_ns,
                        "mode": after.st_mode, "uid": after.st_uid, "gid": after.st_gid}
        except OSError as exc:
            raise ProbeError(type(exc).__name__) from exc


class Collector:
    """Keep digests and failure codes, not raw process/configuration contents."""

    def __init__(self, system: SystemReader):
        self.system = system
        self.evidence: list[Evidence] = []

    def probe(self, operation: str, target):
        ident = f"e{len(self.evidence) + 1}"
        label = json.dumps(target) if isinstance(target, tuple) else target
        try:
            value = getattr(self.system, operation)(target)
            if isinstance(value, CommandResult):
                raw = json.dumps([value.returncode, value.stdout, value.stderr])
                outcome = f"EXIT_{value.returncode}"
            else:
                raw = json.dumps(value, ensure_ascii=True)
                outcome = "OK"
            digest = hashlib.sha256(raw.encode()).hexdigest()
            self.evidence.append(Evidence(ident, operation, label, outcome, digest))
            return value, ident
        except ProbeError as exc:
            self.evidence.append(Evidence(ident, operation, label, str(exc)))
            return None, ident
