"""Interactive orchestration over existing reviewed preparation/repair capabilities.

The UI never grants admission, downloads packages or deploys a probe. Each state
change still requires the exact displayed document hash and native revalidation.
"""
from datetime import datetime, timezone
import json
import re

from .documents import load_document
from .planning import plan
from .preparation import preparation_plan, execute_preparation
from .profiles import php_source_profile
from .repair_policy import build_repair_review
from .repair_execution import decode_plan, execute_repair_review
from .service import scan
from .terminal import explain, render_scan, render_plan
from .system import ProbeError


class Cancelled(Exception):
    pass


class ConfirmationMismatch(Exception):
    pass


class Prompts:
    def __init__(self, terminal, input_stream):
        self.ui = terminal
        self.input = input_stream

    def ask(self, en, zh):
        self.ui.line(self.ui.t(en, zh), tone='heading')
        value = self.input.readline(4097)
        if not value or len(value) > 4096:
            raise Cancelled()
        return value.strip()

    def confirm(self, document, checksum):
        if not re.fullmatch(r'[0-9a-f]{64}', checksum):
            raise ValueError('GUIDED_CONFIRMATION_HASH_INVALID')
        self.ui.line()
        # One logical line keeps the exact digest copyable even on narrow screens.
        print('  Plan SHA256: ' + checksum, file=self.ui.stream)
        answer = self.ask('Paste this complete hash to confirm; d = full review; Enter = cancel:',
                          '粘贴上方完整摘要以确认；输入 d 查看完整审阅；直接回车取消：')
        while answer == 'd':
            render_tree(document, self.ui)
            answer = self.ask('Confirm with the complete hash, or press Enter to cancel:', '输入完整摘要确认，或直接回车取消：')
        if not answer or answer == 'q':
            raise Cancelled()
        if answer != checksum:
            raise ConfirmationMismatch()
        return answer


def render_tree(value, ui, label='Review', depth=0):
    """Full detail is available explicitly, including the bound contract/evidence."""
    ui.line(label, tone='heading', indent=min(2 + depth, 10))
    if isinstance(value, dict):
        for key, child in value.items():
            render_tree(child, ui, str(key), depth + 1)
    elif isinstance(value, (list, tuple)):
        for number, child in enumerate(value, 1):
            render_tree(child, ui, str(number), depth + 1)
    else:
        ui.line(str(value), indent=min(4 + depth, 12))


def review_summary(document, ui):
    proposal = decode_plan(document['plan'])
    ui.header('Confirm package repair', '确认软件包修复')
    ui.line(ui.t('Only the following reviewed changes will be attempted.', '只会尝试执行以下已审阅的变更。'))
    ui.heading('Packages', '软件包')
    for item in proposal.changes:
        ui.line(f'{item.name}: {item.old_version} → {item.new_version}')
    ui.heading('Service interruption', '服务中断')
    contract = document['contract']
    ui.line(ui.t('Services: ', '服务：') + ', '.join(proposal.services))
    ui.line(ui.t('Budget (seconds): ', '停机预算（秒）：') + str(contract['maintenance_budget_seconds']))
    ui.line(ui.t('Package scripts and triggers will run. Services may restart. Automatic rollback is unavailable.',
                 '将运行软件包维护脚本及触发器，服务可能重启；不提供自动回滚。'), tone='warning')
    ui.line(ui.t('Full scripts/configuration identities and evidence are available with d before confirmation.',
                 '确认前可输入 d 查看完整脚本/配置身份及证据。'))
    return proposal


def result_summary(result, ui):
    status = result.get('status', 'BLOCKED')
    ui.heading('Result', '处理结果')
    messages = {
        'VERIFIED_WITHIN_DECLARED_SCOPE': ('Repair verified within the reviewed scope.', '修复已在审阅范围内通过验证。'),
        'PARTIAL': ('Partially completed. System changes remain; inspect the saved result before recovery.', '操作部分完成，系统可能已变更；请先查看保存的结果再进行恢复。'),
        'CANCELLED': ('Cancelled before package repair.', '已取消，未执行软件包修复。'),
        'BLOCKED': ('Repair cannot proceed with the current evidence.', '当前证据不足，无法继续修复。'),
    }
    ui.line(status + ' · ' + ui.t(*messages.get(status, ('Operation did not complete.', '操作未完成。'))),
            tone='heading' if status == 'VERIFIED_WITHIN_DECLARED_SCOPE' else 'warning')
    for reason in dict.fromkeys(result.get('reasons', result.get('blockers', []))):
        ui.line('• ' + explain(str(reason), ui))
    if result.get('preparation_changed'):
        ui.line(ui.t('Preparation already changed service state. Saved receipts are retained; cancellation does not undo it.',
                     '准备步骤已改变服务状态，相关收据已保留；取消不会撤销这些变更。'), tone='warning')
    if result.get('session_directory'):
        ui.line(ui.t('Review and recovery records: ', '审阅与恢复记录：') + result['session_directory'])
    ui.line(ui.t('This is not a global runtime safety guarantee.', '此结果不等于整台系统的安全保证。'), tone='muted')
    ui.line()


def run_guided(*, system, simulator, controller, probe, journal, session_factory, ui,
               input_stream, package_cache, state_directory, budget_seconds=600,
               source_cohort=None, dry_run=False, prepared_receipt=None, review_path=None,
               now=None, scanner=scan, root_allowed=True, details=False):
    clock = (lambda: now) if now else lambda: datetime.now(timezone.utc)
    prompts = Prompts(ui, input_stream)
    session = None; preparation_changed = False; dispatch_started = False

    def stop(reason, status='BLOCKED'):
        return {'status': status, 'changed': preparation_changed or dispatch_started,
                'preparation_changed': preparation_changed, 'reasons': [reason], 'safe': False}

    def save(name, document):
        try:
            return session.write(name, document)
        except (OSError, ValueError):
            # A full disk must not discard the only recovery receipt after a change.
            ui.line(ui.t('Could not save this record. Preserve the following recovery data:',
                         '无法保存记录，请保留以下恢复数据：'), tone='danger')
            print(json.dumps(document, ensure_ascii=True), file=ui.stream)
            raise

    try:
        if type(budget_seconds) is not int or not 60 <= budget_seconds <= 1800:
            return stop('REPAIR_MAINTENANCE_BUDGET_INVALID')
        if review_path:
            document = load_document(system.read_plan_document(review_path))
            proposal = review_summary(document, ui)
            if dry_run:
                return stop('REVIEW_ONLY_NO_CHANGES')
        else:
            report = scanner(system, now=clock(), package_cache=package_cache)
            render_scan(report, ui)
            if not report.inventory.packages:
                return stop('NO_PHP_PACKAGES_OBSERVED_IS_NOT_PROOF_OF_ABSENCE')
            supported = php_source_profile(report.inventory.environment)
            cohort = source_cohort or supported
            selected = [p.id for p in report.inventory.packages if p.source_name == cohort]
            if (not supported or cohort != supported or not selected or report.inventory.environment.scope == 'container'
                    or any(p.architecture not in {'amd64', 'all'} for p in report.inventory.packages if p.id in selected)):
                return stop('GUIDED_REPAIR_ENVIRONMENT_UNSUPPORTED')
            diagnostic = plan(report, system=system, simulator=simulator, now=clock(),
                              target_package_ids=selected, include_components=True)
            if dry_run:
                render_plan(diagnostic, ui, details=details)
                return stop('REVIEW_ONLY_NO_CHANGES')
            # These are the same diagnostic prerequisites required by repair_policy.
            required = {'vendor_rules', 'target_selection', 'archive_chain', 'target_identity',
                        'dependency_changes', 'input_stability', 'evidence_freshness',
                        'diagnostic_simulation', 'package_manager_locks'}
            present = {g.category for g in diagnostic.gates if g.status == 'PASS'}
            if not required <= present:
                render_plan(diagnostic, ui, details=details)
                return stop('GUIDED_PREREQUISITES_INCOMPLETE')
            if not diagnostic.changes:
                return stop('NO_PACKAGE_CHANGES')
            if not input_stream.isatty():
                return stop('INTERACTIVE_TERMINAL_REQUIRED')
            if not root_allowed:
                ui.command('sudo webpatch fix')
                return stop('REPAIR_REQUIRES_LINUX_ROOT')
            if any(value is None for value in (controller, probe, simulator, journal)):
                return stop('REPAIR_CAPABILITIES_REQUIRED')
            if prepared_receipt:
                receipt = load_document(system.read_plan_document(prepared_receipt))
                if prompts.ask('Repeat the receipt’s declared loopback verification requests? [y/N]',
                               '重新请求收据中声明的本机验证探针？[y/N]') != 'y':
                    raise Cancelled()
            else:
                services = sorted({r.service for r in report.inventory.runtimes
                                   if r.service and set(r.package_ids) & set(selected)})
                if not services:
                    return stop('GUIDED_NO_SUPPORTED_RUNNING_SERVICE')
                ui.heading('Service verification', '服务验证')
                ui.line(ui.t('A reviewed WebPatch collector must already be deployed on each target route.',
                             '各目标路由需要先部署经过审阅的 WebPatch 验证探针。'))
                ui.line(ui.t('This wizard does not create a web page or change web-server routing. Enter q to stop.',
                             '向导不会创建网页或修改 Web 路由。输入 q 可退出。'))
                targets = []
                for service in services:
                    pools = [None]
                    if service != 'apache2.service':
                        branch = service.removeprefix('php').removesuffix('-fpm.service')
                        pools = sorted({r.target for r in report.inventory.config_relations
                                        if r.kind == 'fpm_pool' and r.path.startswith(f'/etc/php/{branch}/fpm/')})
                    if not pools:
                        return stop('GUIDED_FPM_POOLS_UNKNOWN')
                    for pool in pools:
                        ui.line(service + (f' · {pool}' if pool else ''), tone='heading')
                        url = prompts.ask('Collector URL (http://127.0.0.1:PORT/path.php):', '探针 URL（http://127.0.0.1:端口/路径.php）：')
                        if not url or url == 'q': raise Cancelled()
                        script = prompts.ask('Root-owned collector file (absolute path):', '由 root 管理的探针文件（绝对路径）：')
                        if not script or script == 'q': raise Cancelled()
                        targets.append({'service': service, 'url': url, 'script': script, 'pool_listener': pool})
                preparation = preparation_plan(report, system=system, services=services, probes=targets,
                                               package_cache=package_cache, state_dir=state_directory, now=clock())
                if preparation['status'] != 'READY_FOR_EXPLICIT_PREPARATION_CONFIRMATION':
                    return {'status': 'BLOCKED', 'changed': False, 'reasons': preparation['blockers'], 'safe': False}
                ui.header('Confirm service preparation', '确认服务准备')
                for service in services: ui.line(service)
                ui.line(ui.t('Create private configuration snapshots and temporary service definitions.',
                             '创建私有配置快照及临时服务定义。'))
                ui.line(ui.t('Reload systemd, restart these services, then request the declared verification probes.',
                             '重新加载 systemd，重启上述服务，再请求已声明的验证探针。'))
                for target in targets:
                    ui.line(target['url'], indent=4)
                    ui.line(target['script'], indent=4, tone='muted')
                ui.line(ui.t('Requests may be interrupted. This step does not install packages.',
                             '请求可能中断。此步骤不会安装软件包。'), tone='warning')
                confirmation = prompts.confirm(preparation, preparation['preparation_sha256'])
                session = session_factory().create()
                save('preparation.json', preparation)
                preparation_changed = True  # dispatch can partially change state even on interruption
                prepared = execute_preparation(preparation, confirmation_sha256=confirmation,
                    system=system, controller=controller, probe=probe, journal=journal, clock=clock, scanner=scanner)
                preparation_changed = bool(prepared.get('changed'))
                save('preparation-result.json', prepared)
                if prepared['status'] != 'VERIFIED_CONTROLLED_STARTUP':
                    return {**prepared, 'safe': False, 'session_directory': str(session.path)}
                receipt = prepared['receipt']
                receipt_path = save('startup.json', receipt)
                ui.line(ui.t('Preparation verified. To continue later:', '准备已验证。如需稍后继续：'))
                # Generated paths contain only fixed components and random hexadecimal IDs.
                ui.command(f'sudo webpatch fix --prepared-receipt {receipt_path} --state-directory {state_directory}')
            current = scanner(system, now=clock(), package_cache=package_cache)
            review = build_repair_review(current, system=system, simulator=simulator, controller=controller,
                probe=probe, startup_receipt=receipt, source_cohort=cohort, package_cache=package_cache,
                budget_seconds=budget_seconds, clock=clock)
            document = review.document()
            proposal = review_summary(document, ui)
        if proposal.admission_status != 'READY_FOR_CONFIRMATION' or proposal.blockers:
            if session: save('review.json', document)
            return {'status': 'BLOCKED', 'changed': preparation_changed, 'preparation_changed': preparation_changed,
                    'reasons': list(proposal.blockers) or [proposal.status], 'safe': False,
                    **({'session_directory': str(session.path)} if session else {})}
        if not input_stream.isatty(): return stop('INTERACTIVE_TERMINAL_REQUIRED')
        if not root_allowed: return stop('REPAIR_REQUIRES_LINUX_ROOT')
        if any(value is None for value in (controller, probe, simulator, journal)):
            return stop('REPAIR_CAPABILITIES_REQUIRED')
        confirmation = prompts.confirm(document, proposal.plan_sha256)
        if session is None: session = session_factory().create()
        save('review.json', document)
        dispatch_started = True
        result = execute_repair_review(document, confirmation_sha256=confirmation,
            system=system, simulator=simulator, controller=controller, probe=probe, journal=journal,
            clock=clock, scanner=scanner)
        result['preparation_changed'] = preparation_changed
        result['session_directory'] = str(session.path)
        save('result.json', result)
        return result
    except (Cancelled, KeyboardInterrupt, EOFError):
        result = stop('CONFIRMATION_CANCELLED', 'PARTIAL' if dispatch_started else 'CANCELLED')
    except ConfirmationMismatch:
        result = stop('EXACT_PLAN_HASH_CONFIRMATION_REQUIRED')
    except (OSError, ValueError, KeyError, TypeError, ProbeError) as exc:
        result = stop('GUIDED_OPERATION_INCOMPLETE:' + type(exc).__name__,
                      'PARTIAL' if preparation_changed or dispatch_started else 'BLOCKED')
    if session: result['session_directory'] = str(session.path)
    return result
