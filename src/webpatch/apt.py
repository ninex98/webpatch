"""Separate, simulation-only capability. Cannot install, refresh or run hooks."""

from dataclasses import dataclass
import os
from pathlib import Path
import selectors
import subprocess
import tempfile
import time
from typing import Protocol

from .system import CommandResult, ProbeError, VERSION
import re

APT_TIMEOUT_SECONDS = 60
MAX_SIMULATION_BYTES = 8 * 1024 * 1024

@dataclass(frozen=True)
class SimulationResult:
    command: tuple[str, ...]
    result: CommandResult
    privileged: bool
    configuration: str = "ISOLATED_NO_HOOKS_SYSTEM_SOURCES_STATUS_AND_PREFERENCES"


class AptSimulator(Protocol):
    def simulate(self, targets: tuple[str, ...]) -> SimulationResult: ...


def simulation_command(targets):
    if not targets or len(targets) > 128 or len(set(targets)) != len(targets):
        raise ProbeError("INVALID_SIMULATION_TARGETS")
    for target in targets:
        match = re.fullmatch(r"([a-z0-9][a-z0-9+.-]*):([a-z0-9][a-z0-9-]*)=(.+)", target)
        if not match or not VERSION.fullmatch(match[3]):
            raise ProbeError("INVALID_SIMULATION_TARGET")
    # --simulate never downloads. --no-download additionally demands cached .debs
    # even during simulation, preventing valid upgrades with an empty archive cache.
    return ("/usr/bin/apt-get", "--simulate", "--no-remove", "--only-upgrade",
            "--no-install-recommends", "install", *targets)


class LocalAptSimulator:
    def _configuration(self, root):
        return (
            f'Dir::Etc::main "/dev/null";\nDir::Etc::parts "{root}/parts";\n'
            'Dir::Etc::sourcelist "/etc/apt/sources.list";\n'
            'Dir::Etc::sourceparts "/etc/apt/sources.list.d";\n'
            'Dir::Etc::preferences "/etc/apt/preferences";\n'
            'Dir::Etc::preferencesparts "/etc/apt/preferences.d";\n'
            'Dir::State::status "/var/lib/dpkg/status";\n'
            'Dir::State::lists "/var/lib/apt/lists";\n'
            'Dir::State::extended_states "/var/lib/apt/extended_states";\n'
            f'Dir::Cache "{root}/cache";\nDir::Cache::archives "{root}/archives";\n'
            f'Dir::Log "{root}/log";\n'
            'Dir::Cache::pkgcache "";\nDir::Cache::srcpkgcache "";\n'
            'APT::Get::Simulate "true";\nDebug::NoLocking "true";\n'
            'APT::Get::AllowUnauthenticated "false";\n'
            'Acquire::AllowInsecureRepositories "false";\n'
            'Acquire::AllowDowngradeToInsecureRepositories "false";\n')

    def simulate(self, targets):
        command = simulation_command(targets)
        # Only tool-owned temporary files are written; system APT dirs stay read-only.
        # Linux-only backend: a fixed parent keeps TMPDIR text out of apt.conf.
        with tempfile.TemporaryDirectory(prefix="webpatch-apt-simulation-", dir="/tmp") as directory:
            root = Path(directory)
            for name in ("parts", "cache", "archives", "log"):
                (root / name).mkdir()
            config = root / "apt.conf"
            config.write_text(self._configuration(root))
            env = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C", "LANG": "C",
                   "APT_CONFIG": str(config), "DEBIAN_FRONTEND": "noninteractive"}
            try:
                with subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, env=env, cwd="/", shell=False) as process:
                    buffers = [bytearray(), bytearray()]
                    deadline = time.monotonic() + APT_TIMEOUT_SECONDS
                    try:
                        with selectors.DefaultSelector() as selector:
                            selector.register(process.stdout, selectors.EVENT_READ, 0)
                            selector.register(process.stderr, selectors.EVENT_READ, 1)
                            while selector.get_map():
                                if time.monotonic() > deadline:
                                    raise ProbeError("APT_SIMULATION_TIMEOUT")
                                for key, _ in selector.select(0.1):
                                    chunk = os.read(key.fileobj.fileno(), 65536)
                                    if not chunk:
                                        selector.unregister(key.fileobj)
                                    else:
                                        buffers[key.data].extend(chunk)
                                        if sum(map(len, buffers)) > MAX_SIMULATION_BYTES:
                                            raise ProbeError("APT_SIMULATION_OUTPUT_LIMIT")
                        process.wait(timeout=max(0.001, deadline - time.monotonic()))
                    except BaseException:
                        process.kill()
                        process.wait()
                        raise
                    result = CommandResult(process.returncode, *(b.decode("utf-8", "strict") for b in buffers))
            except (OSError, UnicodeError, subprocess.TimeoutExpired) as exc:
                raise ProbeError(type(exc).__name__) from exc
        return SimulationResult(command, result, os.geteuid() == 0)
