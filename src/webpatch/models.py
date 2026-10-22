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
    scope_sha256: str | None = None


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


@dataclass(frozen=True)
class EntityRef:
    kind: str
    id: str


@dataclass(frozen=True)
class CoverageCheck:
    id: str
    requirement: str
    status: str  # VERIFIED, OBSERVED, UNKNOWN, UNSUPPORTED, NOT_CHECKED
    subjects: tuple[EntityRef, ...]
    evidence_ids: tuple[str, ...]
    reason: str
    next_step: str
    blocks_repair: bool = True


@dataclass(frozen=True)
class ScanScope:
    id: str
    boundary: str
    completeness: str
    package_ids: tuple[str, ...]
    runtime_ids: tuple[str, ...]
    exclusions: tuple[str, ...]


@dataclass(frozen=True)
class PackageImpact:
    package_id: str
    runtime_ids: tuple[str, ...]
    services: tuple[str, ...]
    coverage_ids: tuple[str, ...]
    completeness: str = "UNKNOWN"


@dataclass(frozen=True)
class PlanScope:
    scan_scope_id: str
    requested_package_ids: tuple[str, ...]
    affected_package_ids: tuple[str, ...]
    observed_runtime_ids: tuple[str, ...]
    unresolved_runtime_ids: tuple[str, ...]
    impacts: tuple[PackageImpact, ...]


@dataclass
class Inventory:
    environment: Environment
    packages: list[Package] = field(default_factory=list)
    runtime_hints: list[RuntimeHint] = field(default_factory=list)
    coverage_gaps: list[str] = field(default_factory=list)
    adapters: list[str] = field(default_factory=list)
    runtimes: list[RuntimeInstance] = field(default_factory=list)
    config_relations: list[ConfigRelation] = field(default_factory=list)
    coverage: list[CoverageCheck] = field(default_factory=list)
    scan_scope: ScanScope | None = None


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
    package_trust: dict | None = None


@dataclass(frozen=True)
class PackageTarget:
    name: str
    architecture: str
    installed_version: str
    version: str
    archive_sha256: str


@dataclass(frozen=True)
class PackageChange:
    operation: str
    name: str
    architecture: str
    old_version: str | None
    new_version: str | None


@dataclass(frozen=True)
class InputBinding:
    operation: str
    target: str
    outcome: str
    sha256: str | None


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
    created_at: str = ""
    expires_at: str = ""
    rule_sha256: str = ""
    state_sha256: str = ""
    plan_sha256: str = ""
    simulation_sha256: str | None = None
    targets: tuple[PackageTarget, ...] = ()
    changes: tuple[PackageChange, ...] = ()
    services: tuple[str, ...] = ()
    interruptions: tuple[str, ...] = ()
    bindings: tuple[InputBinding, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    scope: PlanScope | None = None
    coverage: tuple[CoverageCheck, ...] = ()
