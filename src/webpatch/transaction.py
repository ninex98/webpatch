"""Confirmation and transaction state machine; no OS mutation implementation.

Only a freshly computed Plan and an injected capability enter this module.
Saved JSON commands are never dispatched. UNKNOWN is never approval.
"""
from contextlib import AbstractContextManager
from dataclasses import asdict, dataclass
from datetime import datetime
import json
import os
import stat
from pathlib import Path
from typing import Protocol

from .models import Plan
from .planning import digest

REQUIRED_GATES = frozenset({
    'vendor_rules', 'target_selection', 'source_policy', 'archive_chain', 'target_identity',
    'dependency_changes', 'pin_hold_dpkg', 'apt_special_configuration', 'package_manager_locks',
    'input_stability', 'evidence_freshness', 'diagnostic_simulation', 'installation_equivalence',
    'maintainer_scripts_conffiles', 'service_interruption', 'consumer_completeness',
    'loaded_configuration', 'request_attribution', 'execution_authorization',
})


@dataclass(frozen=True)
class StepResult:
    success: bool
    changed: bool = False
    evidence_sha256: str | None = None
    reason: str = ''


class TransactionBackend(Protocol):
    def locked(self) -> AbstractContextManager: ...
    def revalidate(self, expected: Plan) -> bool: ...
    def install(self, targets) -> StepResult: ...
    def restart(self, service: str) -> StepResult: ...
    def verify(self, expected: Plan) -> StepResult: ...


class Journal(Protocol):
    def append(self, event: dict) -> None: ...
    def events(self) -> list[dict]: ...


class AuditJournal:
    """Bounded, append-only event records with a hash chain; not root attestation."""
    def __init__(self, path):
        self.path = Path(path)

    def events(self):
        try:
            descriptor = os.open(self.path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | os.O_NONBLOCK)
        except FileNotFoundError:
            return []
        with os.fdopen(descriptor, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                    or info.st_mode & 0o077 or info.st_size > 16 * 1024 * 1024):
                raise ValueError('JOURNAL_PATH_SIZE_OR_OWNER_INVALID')
            content = stream.read(16 * 1024 * 1024 + 1)
        if len(content) > 16 * 1024 * 1024:
            raise ValueError('JOURNAL_SIZE_LIMIT')
        records, previous = [], '0' * 64
        for line in content.splitlines():
            record = json.loads(line)
            if set(record) != {'previous_sha256', 'event', 'sha256'} or record['previous_sha256'] != previous:
                raise ValueError('JOURNAL_CHAIN_INVALID')
            if digest({'previous_sha256':previous,'event':record['event']}) != record['sha256']:
                raise ValueError('JOURNAL_DIGEST_MISMATCH')
            previous = record['sha256']
            records.append(record['event'])
        return records

    def append(self, event):
        # Execution owns an external transaction lock; this class never pretends
        # its hash chain itself serializes concurrent package managers.
        previous = '0' * 64
        records = self.events()
        if records:
            with self.path.open('rb') as stream:
                last = stream.read().splitlines()[-1]
            previous = json.loads(last)['sha256']
        record = {'previous_sha256':previous, 'event':event}
        record['sha256'] = digest(record)
        flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0)
        descriptor = os.open(self.path, flags, 0o600)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
                raise ValueError('JOURNAL_PERMISSIONS_TOO_OPEN')
            payload = (json.dumps(record, sort_keys=True, separators=(',', ':')) + '\n').encode()
            if len(payload) > 65536 or info.st_size + len(payload) > 16 * 1024 * 1024:
                raise ValueError('JOURNAL_SIZE_LIMIT')
            offset = 0
            while offset < len(payload):
                written = os.write(descriptor, payload[offset:])
                if written <= 0:
                    raise OSError('JOURNAL_WRITE_FAILED')
                offset += written
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def admission_reasons(proposal, confirmation_sha256, now):
    reasons = []
    values = asdict(proposal)
    stored = values.pop('plan_sha256')
    if digest(dict(values, plan_sha256='')) != stored:
        reasons.append('PLAN_DIGEST_MISMATCH')
    if confirmation_sha256 != stored:
        reasons.append('EXACT_PLAN_HASH_CONFIRMATION_REQUIRED')
    try:
        if not now.tzinfo or not datetime.fromisoformat(proposal.created_at) <= now < datetime.fromisoformat(proposal.expires_at):
            reasons.append('PLAN_EXPIRED_OR_CLOCK_REVERSED')
    except (ValueError, TypeError):
        reasons.append('PLAN_VALIDITY_INVALID')
    if proposal.apt_simulation != 'PASS' or proposal.actions:
        reasons.append('PLAN_NOT_A_SUCCESSFUL_TYPED_SIMULATION')
    # The current planner never emits this state. A future admission policy must
    # prove all requirements before any concrete backend can be reached.
    if proposal.admission_status != 'READY_FOR_CONFIRMATION':
        reasons.append('EXECUTION_ADMISSION_BLOCKED')
    categories = {g.category for g in proposal.gates}
    if not REQUIRED_GATES <= categories:
        reasons.append('REQUIRED_EXECUTION_GATES_MISSING')
    for gate in proposal.gates:
        if gate.category == 'execution_authorization':
            continue  # exact hash checked above, never a supplied boolean
        if gate.status != 'PASS':
            reasons.append('EXECUTION_GATE_NOT_PASSED:' + gate.id)
    if any(c.blocks_repair or c.status != 'VERIFIED' for c in proposal.coverage):
        reasons.append('UNRESOLVED_COVERAGE_BLOCKS_EXECUTION')
    if proposal.blockers:
        reasons.append('PLAN_HAS_UNRESOLVED_BLOCKERS')
    if (not proposal.targets or not proposal.scope or proposal.scope.unresolved_runtime_ids
            or not proposal.scope.impacts or any(i.completeness != 'VERIFIED_WITHIN_DECLARED_SCOPE' for i in proposal.scope.impacts)):
        reasons.append('EXECUTION_SCOPE_OR_TARGETS_INCOMPLETE')
    return tuple(sorted(set(reasons)))


def execute(proposal: Plan, *, confirmation_sha256, backend: TransactionBackend, journal: Journal, clock):
    """Execute each typed stage at most once. No rollback or saved argv execution."""
    now = clock()
    reasons = admission_reasons(proposal, confirmation_sha256, now)
    if reasons:
        return {'status':'BLOCKED','changed':False,'plan_sha256':proposal.plan_sha256,'reasons':reasons}
    changed = False
    phase = 'PRECHECK'
    def record(state, details=None):
        journal.append({'plan_sha256':proposal.plan_sha256, 'state':state,
                        'at':clock().isoformat(), 'details':details or {}})
    def attempt():
        nonlocal changed, phase
        if any(e.get('plan_sha256') == proposal.plan_sha256 for e in journal.events()):
            return {'status':'BLOCKED','changed':False,'plan_sha256':proposal.plan_sha256,
                    'reasons':('PLAN_ALREADY_ATTEMPTED_REQUIRES_NEW_REVIEW',)}
        record('PRECHECK')
        if (admission_reasons(proposal, confirmation_sha256, clock()) or not backend.revalidate(proposal)
                or admission_reasons(proposal, confirmation_sha256, clock())):
            record('ABORTED', {'reason':'LOCKED_REVALIDATION_FAILED'})
            return {'status':'BLOCKED','changed':False,'plan_sha256':proposal.plan_sha256,
                    'reasons':('LOCKED_REVALIDATION_FAILED',)}
        phase = 'INSTALLING'
        record(phase)
        changed = True  # an interrupted package manager may have mutated state
        result = backend.install(proposal.targets)
        changed = result.changed
        record('INSTALL_RESULT', asdict(result))
        if not result.success:
            status = 'PARTIAL' if changed else 'FAILED'
            record(status)
            return {'status':status,'changed':changed,'plan_sha256':proposal.plan_sha256,
                    'reasons':('PACKAGE_OPERATION_FAILED',)}
        phase = 'RESTARTING'
        for service in proposal.services:
            record(phase, {'service':service})
            previous_changed, changed = changed, True
            result = backend.restart(service)
            changed = previous_changed or result.changed
            record('RESTART_RESULT', {'service':service, **asdict(result)})
            if not result.success:
                record('RESTART_REQUIRED')
                return {'status':'RESTART_REQUIRED','changed':changed,'plan_sha256':proposal.plan_sha256,
                        'reasons':('SERVICE_RESTART_FAILED',)}
        phase = 'VERIFYING'
        record(phase)
        verification = backend.verify(proposal)
        record('VERIFICATION_RESULT', asdict(verification))
        status = 'VERIFIED_WITHIN_DECLARED_SCOPE' if verification.success else ('PARTIAL' if changed else 'FAILED')
        record(status)
        return {'status':status,'changed':changed,'plan_sha256':proposal.plan_sha256,
                'reasons':() if verification.success else ('POST_REPAIR_VERIFICATION_FAILED',)}

    def failed(exc, can_record):
        status = 'PARTIAL' if changed else 'FAILED'
        details = {'exception_type':type(exc).__name__, 'phase':phase}
        if can_record:
            try:
                record(status, details)
            except Exception:
                details['journal_write_failed'] = True
        else:
            details['journal_write_failed'] = True
        return {'status':status,'changed':changed,'plan_sha256':proposal.plan_sha256,
                'reasons':('TRANSACTION_FAILED',), 'failure':details}

    try:
        with backend.locked():
            try:
                return attempt()
            except Exception as exc:
                return failed(exc, True)
    except Exception as exc:
        # Lock acquisition/release failed: do not write into another owner's log.
        return failed(exc, False)
