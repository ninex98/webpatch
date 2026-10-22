"""Review requirements, not an execution authorization policy.

An individually passing gate proves only its stated condition. Future execution
must supply missing evidence and a separate confirmation/transaction capability.
"""
from datetime import datetime, timedelta
import hashlib
import json

from .coverage import ref
from .models import ReviewGate


def evidence_deadline(report, now):
    bounds = [now + timedelta(minutes=30), datetime.fromisoformat(report.rule_valid_until),
              datetime.fromisoformat(report.observed_at) + timedelta(minutes=30)]
    for candidate in (report.package_trust or {}).get('candidates', []):
        value = candidate.get('valid_until')
        if value:
            bounds.append(datetime.fromisoformat(value))
    if not all(t.tzinfo for t in bounds):
        raise ValueError('EVIDENCE_VALIDITY_TIMEZONE_REQUIRED')
    return min(bounds)


def review_gates(report, proposal, now):
    gates = []
    scope = (ref('scope', proposal.scope.scan_scope_id),)
    scan_ids = tuple(e.id for e in report.evidence)
    source_ids = tuple((report.apt_sources or {}).get('evidence_ids', []))
    trust = report.package_trust or {}
    trust_ids = tuple(trust.get('evidence_ids', []))
    plan_ids = tuple(e.id for e in proposal.evidence)
    blockers = proposal.blockers
    def add(category, status, reason, action, subjects=scope, ids=()):
        key = json.dumps([category, [(s.kind, s.id) for s in subjects]])
        gates.append(ReviewGate(hashlib.sha256(key.encode()).hexdigest(), category, status,
                                tuple(subjects), tuple(sorted(set(ids))), reason, action))
    def matches(prefixes):
        return [b for b in blockers if b.startswith(prefixes)]
    def decision(category, failures, reason, action, ids, checked=True):
        add(category, 'BLOCKED' if failures else ('PASS' if checked else 'NOT_RUN'),
            '; '.join(failures) if failures else reason, action, ids=ids)

    selected = set(proposal.scope.requested_package_ids)
    engines = {p.id for p in report.inventory.packages if p.sapi in {'cli', 'fpm', 'apache2', 'cgi'}}
    assessments = [a for a in report.assessments if a.package_id in selected & engines]
    unknown = [a for a in assessments if a.version_status == 'UNKNOWN']
    rule_errors = matches(('RULE_', 'PLAN_RULES_', 'PACKAGE_ASSESSMENT_'))
    add('vendor_rules', 'PASS' if assessments and not unknown and not rule_errors else 'UNKNOWN',
        'Vendor comparisons have dated rules; BELOW_VENDOR_FIX identifies work, MEETS_VENDOR_FIX is not runtime safety.'
        if not unknown else '; '.join(sorted({a.reason for a in unknown})),
        'Review official advisories, source/release applicability and rule validity; never extend dates without review.',
        ids=[e for a in assessments for e in a.evidence_ids])
    decision('target_selection', matches(('TARGET_NOT_', 'TARGET_PACKAGE_', 'NO_TRUSTED_', 'AMBIGUOUS_CANDIDATE_')),
             'Selected packages and exact same-branch targets are explicit; impact includes all observed consumers.',
             'Select supported package:architecture targets and account for all shared-package consumers.', scan_ids,
             checked=bool(proposal.targets))
    source_blockers = (report.apt_sources or {}).get('blockers', [])
    policy_errors = [b for b in source_blockers if not b.startswith(('APT_PIN_', 'APT_HOOKS_', 'APT_CONFIGURATION_', 'HELD_', 'DPKG_'))]
    decision('source_policy', policy_errors, 'Direct official source policy checked; authentication is a separate gate.',
             'Use reviewed official same-release sources and resolve inaccessible source inputs.', source_ids,
             checked=bool(report.apt_sources))
    decision('archive_chain', trust.get('blockers', []), 'Existing signed Release/Packages chain authenticated.',
             'Supply fresh signed indexes and matching archives; do not bypass signatures or hashes.', trust_ids,
             checked=trust.get('status') == 'VERIFIED_INDEX_CHAIN')
    target_records = [c for c in trust.get('candidates', []) if any(
        (c['name'], c['architecture'], c['version'], c['sha256']) == (t.name, t.architecture, t.version, t.archive_sha256)
        and c['fresh_for_plan'] for t in proposal.targets)]
    target_ok = len({(c['name'], c['architecture']) for c in target_records}) == len(proposal.targets) and bool(proposal.targets)
    add('target_identity', 'PASS' if target_ok else 'UNKNOWN',
        'Every exact target is bound to a signed archive digest.' if target_ok else 'One or more exact targets lack authenticated identity.',
        'Authenticate every selected target and reject conflicting archive hashes.',
        subjects=tuple(ref('package', t.name + ':' + t.architecture) for t in proposal.targets) or scope,
        ids=[e for c in target_records for e in c.get('evidence_ids', [])])
    for c in proposal.coverage:
        status = 'PASS' if c.status == 'VERIFIED' and not c.blocks_repair else (
            c.status if c.status in {'UNKNOWN', 'UNSUPPORTED', 'NOT_CHECKED'} else 'UNKNOWN')
        if status == 'NOT_CHECKED': status = 'NOT_RUN'
        add('coverage:' + c.requirement, status, c.reason, c.next_step, c.subjects, c.evidence_ids)
    dependency_errors = matches(('PACKAGE_REMOVAL_', 'NEW_DEPENDENCY_', 'REINSTALL_', 'DOWNGRADE_', 'UNAPPROVED_DEPENDENCY_',
                                 'SIMULATION_TARGET_', 'DEPENDENCY_ORIGIN_', 'REQUESTED_UPGRADE_'))
    decision('dependency_changes', dependency_errors, 'All parsed dependency operations match the exact approved target set; no unsupported changes.',
             'Reject removal/downgrade/migration; explicitly review identities and approve an exact target set before regenerating.',
             plan_ids, checked=proposal.apt_simulation == 'PASS')
    decision('pin_hold_dpkg', [b for b in source_blockers if b.startswith(('APT_PIN_', 'HELD_', 'DPKG_'))],
             'No observed holds, pins, diversions, pending or unconfigured dpkg states.',
             'Resolve holds/pins and incomplete dpkg state under separate authorization, then rescan.', source_ids,
             checked=bool(report.apt_sources))
    decision('apt_special_configuration', [b for b in source_blockers if b.startswith(('APT_HOOKS_', 'APT_CONFIGURATION_'))],
             'No known special APT hooks/overrides observed by the bounded audit.',
             'Review every hook/override and its install-time effects; isolated simulation deliberately omits these.', source_ids,
             checked=bool(report.apt_sources))
    decision('package_manager_locks', matches(('APT_LOCK_', 'PACKAGE_MANAGER_LOCK_')),
             'No held package-manager lock observed at both simulation boundaries; this is not a held execution lock.',
             'Wait for the owning transaction to finish; future execution must acquire locks and recheck state.', plan_ids,
             checked=any(e.target == '/proc/locks' for e in proposal.evidence))
    decision('input_stability', matches(('STATE_', 'SCOPE_IDENTITY_', 'PLAN_EVIDENCE_')),
             'Observed inputs and runtime identities agree at simulation boundaries.',
             'Rescan after drift and repeat simulation; concurrent transaction protection is still required.', scan_ids + plan_ids,
             checked=proposal.apt_simulation == 'PASS')
    deadline = datetime.fromisoformat(proposal.expires_at)
    add('evidence_freshness', 'PASS' if datetime.fromisoformat(report.observed_at) <= now < deadline else 'BLOCKED',
        'Plan deadline is bounded by scan age, vendor rules and every authenticated index validity window: ' + proposal.expires_at,
        'Reacquire authorized evidence and regenerate the plan before the earliest expiry.', ids=trust_ids)
    add('diagnostic_simulation', proposal.apt_simulation if proposal.apt_simulation != 'FAIL' else 'BLOCKED',
        'APT dependency resolution only; no download, installation or hook execution.',
        'Resolve diagnostic errors and rerun exact targets in the same scope.', ids=plan_ids)
    add('installation_equivalence', 'UNKNOWN',
        'Isolated simulation omits system hooks and parts of special APT configuration; real install behavior is not established.',
        'Review effective installation configuration and its differences from this diagnostic simulator.', ids=source_ids)
    add('maintainer_scripts_conffiles', 'NOT_RUN',
        'Candidate maintainer scripts, triggers and conffile decisions have not been reviewed for installation effects.',
        'Authenticate and review exact candidate control archives, triggers and conffile policy before execution.', ids=trust_ids)
    add('service_interruption', 'UNKNOWN',
        'Affected observed services: ' + ', '.join(proposal.services) + '; maintainer scripts may restart them before explicit restart.',
        'Approve a downtime budget for every consumer, drain strategy and tested manual recovery; no automatic rollback guarantee.')
    add('execution_authorization', 'NOT_RUN', 'No executor or plan-hash confirmation capability exists in this stage.',
        'Implement the separately reviewed phase-three transaction/confirmation contract; apply remains disabled.')
    return tuple(gates)


def review_status(gates):
    required = {'vendor_rules', 'target_selection', 'target_identity', 'source_policy', 'archive_chain',
                'dependency_changes', 'input_stability', 'evidence_freshness', 'diagnostic_simulation'}
    return 'READY_FOR_REVIEW' if all(next(g.status for g in gates if g.category == c) == 'PASS' for c in required) else 'INCOMPLETE'
