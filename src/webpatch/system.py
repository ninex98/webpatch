"""The only production OS boundary; there is deliberately no write interface."""

import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import subprocess
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


def validate_command(argv: tuple[str, ...]) -> None:
    if argv == DPKG_QUERY:
        return
    if (len(argv) == 5 and argv[:2] == ("/usr/bin/dpkg", "--compare-versions")
            and argv[3] == "ge" and VERSION.fullmatch(argv[2])
            and VERSION.fullmatch(argv[4])):
        return
    raise PolicyError("COMMAND_NOT_ALLOWLISTED")


class LocalSystem:
    """Bounded reads and fixed argv, no shell, network or inherited command config."""

    def run(self, argv: tuple[str, ...]) -> CommandResult:
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
                                if sum(map(len, buffers)) > MAX_COMMAND_BYTES:
                                    raise ProbeError("COMMAND_OUTPUT_LIMIT")
                    proc.wait(timeout=max(0.001, deadline - time.monotonic()))
                except BaseException:
                    proc.kill()
                    proc.wait()
                    raise
                return CommandResult(proc.returncode, *(b.decode("utf-8", "strict") for b in buffers))
        except (OSError, UnicodeError, subprocess.TimeoutExpired) as exc:
            raise ProbeError(type(exc).__name__) from exc

    def read_text(self, path: str) -> str:
        try:
            with Path(path).open("rb") as stream:
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
