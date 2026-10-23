"""Human presentation only: no discovery, filesystem writes or repair decisions."""
import os
import shutil
import sys
import unicodedata

from . import __version__


def clean(value):
    """Keep observed paths/names from injecting terminal controls or bidi formatting."""
    return ''.join(f'\\u{ord(c):04x}' if unicodedata.category(c).startswith('C') else c
                   for c in str(value))


def width(text):
    return sum(0 if unicodedata.combining(c) else 2 if unicodedata.east_asian_width(c) in 'WF' else 1
               for c in text)


class Terminal:
    def __init__(self, *, stream=None, lang='auto', color='auto', columns=None):
        self.stream = stream if stream is not None else sys.stdout
        locale = os.environ.get('LC_ALL') or os.environ.get('LC_MESSAGES') or os.environ.get('LANG', '')
        self.zh = lang == 'zh' or (lang == 'auto' and locale.lower().startswith('zh'))
        self.columns = max(24, min(100, columns or shutil.get_terminal_size((88, 24)).columns))
        self.color = color == 'always' or (color == 'auto' and self.stream.isatty()
                     and 'NO_COLOR' not in os.environ and os.environ.get('TERM') != 'dumb')

    def t(self, en, zh):
        return zh if self.zh else en

    def line(self, text='', *, tone=None, indent=2):
        # Wrap before adding our own ANSI codes. Never trust ANSI from observations.
        text = clean(text)
        available = self.columns - indent
        lines = []; current = ''
        for char in text:
            if current and width(current + char) > available:
                split = current.rfind(' ')
                if split > available // 3:
                    lines.append(current[:split]); current = current[split+1:]
                else:
                    lines.append(current); current = ''
            current += char
        lines.append(current)
        codes = {'title': '1;36', 'heading': '1', 'warning': '1;33', 'danger': '1;31', 'muted': '2'}
        for row in lines:
            if tone and self.color:
                row = f'\033[{codes[tone]}m{row}\033[0m'
            print(' ' * indent + row if text else '', file=self.stream)

    def heading(self, en, zh):
        self.line(); self.line(self.t(en, zh), tone='heading')

    def header(self, en, zh):
        self.line(); self.line(f'WebPatch {__version__}  /  {self.t(en, zh)}', tone='title')
        self.line('─' * (self.columns - 4), tone='muted')

    def command(self, command):
        self.line(command, indent=4, tone='title')


def explain(code, terminal):
    """Translate known blockers without inventing a diagnosis for future codes."""
    messages = [
        ('RULES_EXPIRED', 'Advisory rules have expired or the system clock predates review. Update reviewed rules and check the clock.', '规则已过期，或系统时间早于规则审阅时间。请更新已审阅规则并检查系统时间。'),
        ('CLOCK_BEFORE', 'The system clock predates the rule review.', '系统时间早于规则审阅时间。'),
        ('NO_PHP_PACKAGES', 'No managed PHP packages were found; custom PHP or containers may still exist.', '未发现受包管理器管理的 PHP；仍可能存在自编译 PHP 或容器。'),
        ('EMPTY_PACKAGE_INVENTORY', 'No managed runtime packages were found. This does not prove absence.', '未发现受管理的运行时包；这不能证明运行时不存在。'),
        ('CONDITIONAL_WEB_CONFIGURATION', 'Conditional web-server configuration could not be resolved.', 'Web 服务器存在无法解析的条件配置。'),
        ('CONFIGURATION_NOT_PROVEN', 'The configuration actually loaded by services has not been verified.', '尚未验证服务实际加载的配置。'),
        ('HTTP_ROUTING', 'Application routes require an explicitly configured verification probe.', '应用路由需要显式配置的验证探针。'),
        ('RUNNING_IMAGES', 'Running processes and their web routes have not been fully verified.', '尚未完整验证运行中的进程及其 Web 路由。'),
        ('OTHER_CONTAINERS', 'Other containers are outside this scan. Run WebPatch inside each target container.', '其他容器不在本次扫描范围内，请在目标容器内部单独扫描。'),
        ('DISCOVERY_NOT_EXHAUSTIVE', 'Hidden processes and custom installation paths may not be visible.', '隐藏进程和自定义安装路径可能不可见。'),
        ('PACKAGE_ORIGIN', 'Package origin and installed file bytes are not authenticated yet.', '尚未认证包来源及已安装文件的字节身份。'),
        ('VENDOR_BYTES', 'Vendor package bytes and loaded libraries are not authenticated.', '尚未认证厂商包字节与已加载库。'),
        ('PACKAGE_QUERY', 'The package inventory could not be read completely.', '无法完整读取软件包清单。'),
        ('CUSTOM_', 'A custom installation needs a separate review; APT repair is unavailable for it.', '自定义安装需要单独核实，不能使用 APT 修复。'),
        ('NPM_DEPENDENCIES', 'npm application dependencies are outside this runtime scan.', '此运行时扫描不包含 npm 应用依赖。'),
        ('CONTAINER', 'Container images require a rebuild; in-place repair is unavailable.', '容器镜像需要重建，不支持在容器内原地修复。'),
        ('UNSUPPORTED', 'This environment or capability is outside the supported repair scope.', '此环境或能力不在受支持的修复范围内。'),
        ('SOURCE_POLICY', 'Package sources or package-manager configuration need review.', '软件源或包管理器配置需要核实。'),
        ('ARCHIVE', 'Authenticated package archives are missing or could not be verified.', '缺少已认证的软件包归档，或归档无法通过验证。'),
        ('LOCK', 'The package manager is busy or its lock state cannot be verified.', '包管理器正在使用中，或无法验证其锁状态。'),
        ('UNPREPARED', 'Affected services need verified preparation before package repair.', '受影响的服务需要先完成经验证的准备步骤。'),
        ('NO_PACKAGE_CHANGES', 'No admitted package upgrade is available in the current review.', '当前审阅没有可执行的软件包升级。'),
    ]
    for fragment, en, zh in messages:
        if fragment in code:
            return terminal.t(en, zh)
    return terminal.t('Additional verification is required: ', '还需核实：') + str(code)


def render_scan(report, terminal, *, details=False, node=False):
    ui = terminal; inventory = report.inventory
    runtime = 'Node.js' if node else 'PHP'
    ui.header(f'{runtime} security check', f'{runtime} 安全检查')
    env = inventory.environment
    scope = ui.t('current container', '当前容器') if env.scope == 'container' else ui.t('current system scope', '当前系统作用域')
    ui.line(f'{env.os_id.title()} {env.version_id}  ·  {scope}', tone='muted')
    affected = {a.package_id for a in report.assessments if a.version_status == 'BELOW_VENDOR_FIX'}
    unknown = {a.package_id for a in report.assessments if a.version_status == 'UNKNOWN'}
    ui.heading('Result', '检查结果')
    if affected:
        ui.line(ui.t(f'ATTENTION  ·  {len(affected)} potentially affected package(s)',
                     f'需要处理  ·  {len(affected)} 个软件包可能受影响'), tone='danger')
    else:
        ui.line(ui.t('UNKNOWN  ·  Runtime safety is not established', 'UNKNOWN  ·  尚不能确认运行时安全'), tone='warning')
    if not inventory.packages:
        if inventory.runtime_hints or inventory.runtimes:
            ui.line(ui.t(f'{runtime} runtime hints exist, but no managed packages were identified.',
                         f'发现了 {runtime} 运行时线索，但未识别到受管理的软件包。'))
        else:
            ui.line(ui.t(f'No {runtime} packages or runtime hints were found.', f'未发现 {runtime} 软件包或运行时线索。'))
        ui.line(ui.t('An empty inventory does not prove the runtime is absent.', '空清单不代表运行时不存在。'))
    elif not affected:
        ui.line(ui.t('Package versions alone cannot verify running services.', '仅凭软件包版本，不能确认运行中的服务是否安全。'))
    ui.line(ui.t(f'{len(inventory.packages)} packages  ·  {len(inventory.runtimes)} observed processes  ·  {len(unknown)} package versions unknown',
                 f'{len(inventory.packages)} 个软件包  ·  {len(inventory.runtimes)} 个已观察进程  ·  {len(unknown)} 个包版本状态未知'))
    if inventory.packages:
        ui.heading('Packages', '软件包')
        packages = sorted(inventory.packages, key=lambda p: (p.id not in affected, p.id not in unknown, p.id))
        for package in packages if details else packages[:8]:
            rows = [a for a in report.assessments if a.package_id == package.id]
            label = ui.t('UPDATE NEEDED', '需要更新') if package.id in affected else (
                ui.t('UNKNOWN', '未知') if not rows or package.id in unknown else ui.t('VERSION MEETS FIX', '版本达到修复线'))
            ui.line(f'{package.name}  [{label}]', tone='warning' if package.id in affected else None)
            ui.line(ui.t('Installed: ', '已安装：') + package.version, indent=4)
            if package.id in affected:
                fixes = sorted({a.fixed_version for a in rows if a.version_status == 'BELOW_VENDOR_FIX' and a.fixed_version})
                ui.line(ui.t('Vendor fix: ', '厂商修复线：') + ', '.join(fixes), indent=4)
                ui.line(', '.join(sorted({a.cve for a in rows if a.version_status == 'BELOW_VENDOR_FIX'})), indent=4, tone='muted')
        if not details and len(packages) > 8:
            ui.line(ui.t(f'+ {len(packages)-8} more packages; use --details.', f'另有 {len(packages)-8} 个包；使用 --details 展开。'), tone='muted')
    ui.heading('What still needs checking', '尚需核实')
    gaps = sorted(set(inventory.coverage_gaps))
    expired = [g for g in gaps if 'RULES_EXPIRED' in g or 'CLOCK_BEFORE' in g]
    unreadable = [e for e in report.evidence if 'Permission' in e.outcome or 'READ_UNAVAILABLE' in e.outcome]
    summaries = [explain(g, ui) for g in expired]
    if unreadable:
        summaries.append(ui.t('Some reads were denied. Run a privileged read-only scan if you administer this system.',
                             '部分读取被拒绝。如果你管理此系统，可使用 sudo 重新只读扫描。'))
    if inventory.packages:
        summaries.append(ui.t('Package authenticity, loaded configuration and request routing still need verification.',
                             '仍需验证包真实性、实际加载配置和请求路由。'))
    if not node and any('CONDITIONAL_WEB_CONFIGURATION' in g for g in gaps):
        summaries.append(explain('CONDITIONAL_WEB_CONFIGURATION', ui))
    summaries.append(ui.t('Custom installations, hidden processes and other containers are not fully covered.',
                         '自定义安装、隐藏进程和其他容器尚未完整覆盖。'))
    if node:
        summaries.append(explain('NPM_DEPENDENCIES', ui))
    for summary in dict.fromkeys(summaries):
        ui.line('• ' + summary)
    if details:
        ui.heading('Evidence details', '证据详情')
        for gap in gaps:
            ui.line(explain(gap, ui)); ui.line(gap, indent=4, tone='muted')
        for check in inventory.coverage:
            if check.requirement.startswith(('adapter_limit:', 'node:')):
                continue
            ui.line(f'[{check.status}] {check.requirement}')
            ui.line(check.reason, indent=4)
            ui.line(ui.t('Next: ', '下一步：') + check.next_step, indent=4)
            for subject in check.subjects:
                ui.line(f'{subject.kind}: {subject.id}', indent=4, tone='muted')
    ui.heading('Next step', '下一步')
    command = 'scan-node' if node else 'scan'
    if not inventory.packages:
        ui.line(ui.t(f'Confirm where {runtime} is installed. For containers, scan inside the target container.',
                     f'先确认 {runtime} 安装在哪里；如果使用容器，请在目标容器内部扫描。'))
        ui.line(ui.t('No package repair is available from this inventory.', '当前清单没有可供修复的软件包。'))
    elif affected and not node:
        ui.line(ui.t('Review a read-only upgrade plan:', '查看只读升级计划：'))
        ui.command('webpatch plan')
    else:
        ui.line(ui.t('Review the remaining evidence gaps before making changes.', '先核实剩余证据缺口，再决定是否变更。'))
    if not details:
        ui.command(f'webpatch {command} --details')
    ui.line(); ui.line(ui.t('Read-only · no system changes', '只读检查 · 未修改系统'), tone='muted')
    ui.line(ui.t('Rules valid until: ', '规则有效期：') + report.rule_valid_until, tone='muted')
    ui.line()


def render_plan(plan, ui, *, details=False):
    ui.header('Upgrade review', '升级审阅')
    ui.line(ui.t('BLOCKED · review only, no changes authorized', 'BLOCKED · 仅供审阅，尚未授权变更'), tone='warning')
    ui.line(ui.t('APT simulation: ', 'APT 模拟：') + plan.apt_simulation)
    ui.heading('Proposed changes', '计划变更')
    if not plan.changes:
        ui.line(ui.t('No verified upgrade proposal is available.', '当前没有已验证的升级方案。'))
    for change in plan.changes:
        ui.line(f'{change.name}: {change.old_version or "—"} → {change.new_version or "—"}')
    ui.heading('Why this cannot run yet', '尚不能执行的原因')
    reasons = list(dict.fromkeys(explain(b, ui) for b in plan.blockers))
    for reason in reasons if details else reasons[:5]:
        ui.line('• ' + reason)
    if not details and len(reasons) > 5:
        ui.line(ui.t(f'+ {len(reasons)-5} additional checks; use --details.', f'另有 {len(reasons)-5} 项待核实；使用 --details 展开。'))
    if details:
        ui.heading('Review gates', '审阅门禁')
        for gate in plan.gates:
            ui.line(f'[{gate.status}] {gate.category}')
            ui.line(gate.reason, indent=4)
            ui.line(gate.required_action, indent=4)
        ui.line(ui.t('Plan hash: ', '计划摘要：') + plan.plan_sha256)
    ui.heading('Next step', '下一步')
    ui.line(ui.t('Resolve the listed evidence gaps before confirming any repair.', '先解决上述证据缺口，再确认修复。'))
    if not details:
        ui.command('webpatch plan --details')
    ui.line(); ui.line(ui.t('Read-only · no package installation or service restart', '只读审阅 · 未安装软件包或重启服务'), tone='muted'); ui.line()
