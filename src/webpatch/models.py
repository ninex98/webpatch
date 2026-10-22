"""Serializable contracts shared by discovery, rules and planning."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Evidence:
    id: str
    operation: str
    target: str
    outcome: str
    sha256: str | None = None


@dataclass(frozen=True)
class Environment:
    os_id: str
    version_id: str
    codename: str
    scope: str
    mount_namespace: str | None


@dataclass(frozen=True)
class Package:
    name: str
    version: str
    architecture: str
    source_name: str
    source_version: str
    status: str
    sapi: str
    evidence_id: str
    provenance: str = "UNVERIFIED_LOCAL_METADATA"

    @property
    def id(self) -> str:
        return f"{self.name.split(':')[0]}:{self.architecture}"


@dataclass(frozen=True)
class RuntimeHint:
    kind: str
    path: str | None
    pid: int | None
    scope: str
    evidence_ids: tuple[str, ...]
    deleted: bool = False
    verification: str = "UNKNOWN"


@dataclass(frozen=True)
class RuntimeInstance:
    pid: int
    sapi: str
    path: str | None
    package_ids: tuple[str, ...]
    service: str | None
    start_ticks: str | None
    file_sha256: str | None
    association: str
    blockers: tuple[str, ...]
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class ConfigRelation:
    kind: str
    path: str
    name: str
    target: str
    status: str
    evidence_ids: tuple[str, ...]


@dataclass
class Inventory:
    environment: Environment
    packages: list[Package] = field(default_factory=list)
    runtime_hints: list[RuntimeHint] = field(default_factory=list)
    coverage_gaps: list[str] = field(default_factory=list)
    adapters: list[str] = field(default_factory=list)
    runtimes: list[RuntimeInstance] = field(default_factory=list)
    config_relations: list[ConfigRelation] = field(default_factory=list)


@dataclass(frozen=True)
class Assessment:
    package_id: str
    cve: str
    version_status: str
    reason: str
    fixed_version: str | None
    references: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    runtime_status: str = "UNKNOWN"


@dataclass(frozen=True)
class Report:
    schema_version: int
    observed_at: str
    rule_revision: str
    rule_sha256: str
    rule_valid_until: str
    inventory: Inventory
    assessments: list[Assessment]
    evidence: list[Evidence]
    overall: str
    safe: bool = False
    apt_sources: dict | None = None


@dataclass(frozen=True)
class Plan:
    schema_version: int
    status: str
    executable: bool
    apt_simulation: str
    report_sha256: str
    blockers: tuple[str, ...]
    recommendations: tuple[str, ...]
    actions: tuple[str, ...] = ()
