#!/usr/bin/env python3
"""Regenerate small, self-contained README SVGs from the recorded CLI capture.

Standard library only. Never runs a scan or fabricates command output.
"""
from html import escape
import json
from pathlib import Path
import textwrap

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
CAPTURE = ROOT / 'evidence/readme-design/cli/capture.json'
SANS = "'Avenir Next', Avenir, 'Segoe UI', sans-serif"
MONO = "'SFMono-Regular', Consolas, 'Liberation Mono', monospace"


def text(x, y, content, size=16, color='#c5d3e5', weight=400, mono=False, extra=''):
    return (f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" '
            f'font-weight="{weight}" font-family="{MONO if mono else SANS}" {extra}>'
            f'{escape(content)}</text>')


def svg(name, w, h, title, body, description=''):
    data = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" role="img" aria-labelledby="title desc">\n'
            f'<title id="title">{escape(title)}</title>\n'
            f'<desc id="desc">{escape(description or title)}</desc>\n{body}\n</svg>\n')
    (OUT / name).write_text(data)


def mark(x, y, scale=1, color='#49d8ed'):
    # A broken W trace and a replaceable square: a patch without a safety checkmark.
    return (f'<g transform="translate({x} {y}) scale({scale})">'
            f'<path d="M12 18 25 65 44 39 62 65 73 29" fill="none" '
            f'stroke="{color}" stroke-width="9" stroke-linejoin="bevel"/>'
            f'<path d="M69 11h13v13H69z" fill="{color}"/></g>')


svg('logo.svg', 96, 96, 'WebPatch logo',
    '<rect x="1" y="1" width="94" height="94" rx="22" fill="#0b172b" stroke="#29435a"/>'
    + mark(3, 8), 'An original geometric W trace with a separate square patch. Editable vector artwork.')

for dark in (False, True):
    theme = 'dark' if dark else 'light'
    bg, ink, muted, line, accent = (
        ('#091426', '#f0f6fc', '#a9bdd2', '#223c55', '#55dfed') if dark else
        ('#f0f6fa', '#102840', '#476079', '#cadce7', '#007a92'))
    for mobile in (False, True):
        w, h = (480, 290) if mobile else (1120, 350)
        body = f'<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="18" fill="{bg}" stroke="{line}"/>'
        if mobile:
            body += mark(27, 36, .62, accent)
            body += text(94, 78, 'WebPatch', 39, ink, 650)
            body += text(32, 133, 'Evidence before action.', 28, ink, 550)
            body += text(32, 169, 'PHP runtime security, grounded in evidence.', 17, muted)
            body += f'<path d="M32 201H448" stroke="{line}"/>'
            body += text(32, 235, 'DISCOVER', 12, accent, 600, extra='letter-spacing="1.5"')
            body += text(168, 235, 'ASSESS', 12, accent, 600, extra='letter-spacing="1.5"')
            body += text(290, 235, 'REVIEW', 12, accent, 600, extra='letter-spacing="1.5"')
            body += text(32, 268, 'READ-ONLY PREVIEW / EXECUTION DISABLED', 11, muted, 500, mono=True)
        else:
            body += '<defs><pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse"><path d="M32 0H0V32" fill="none" stroke="' + line + '" stroke-width=".6"/></pattern></defs>'
            body += '<rect x="710" y="1" width="409" height="348" rx="18" fill="url(#grid)" opacity=".45"/>'
            body += mark(42, 53, .8, accent)
            body += text(127, 109, 'WebPatch', 57, ink, 650, extra='letter-spacing="-2"')
            body += text(48, 177, 'Evidence before action.', 38, ink, 550, extra='letter-spacing="-.7"')
            body += text(48, 218, 'PHP runtime security, grounded in evidence.', 21, muted)
            body += f'<path d="M48 263H653" stroke="{line}"/>'
            body += text(48, 300, 'READ-ONLY PREVIEW', 12, accent, 600, extra='letter-spacing="2"')
            body += text(313, 300, 'DISCOVER / ASSESS / REVIEW', 12, muted, 500, mono=True)
            for i, (label, sub) in enumerate((('Local evidence', 'Packages / processes / services'), ('Vendor context', 'Distribution-aware assessments'), ('Reviewable plans', 'Execution remains disabled'))):
                y = 51 + i * 88
                body += f'<rect x="750" y="{y}" width="322" height="71" rx="8" fill="{bg}" stroke="{line}"/>'
                body += text(767, y+30, f'0{i+1}', 13, accent, 600, mono=True)
                body += text(804, y+30, label, 18, ink, 550)
                body += text(804, y+53, sub, 12, muted)
                if i < 2:
                    body += f'<path d="M783 {y+71}v17" stroke="{accent}" stroke-width="2"/>'
        svg(f'hero-{"mobile-" if mobile else ""}{theme}.svg', w, h,
            'WebPatch — Evidence before action.', body,
            'Read-only PHP runtime security inventory. Discover local evidence, assess vendor context, review plans. Execution remains disabled.')

for filename, label, width in [('preview-badge.svg', '0.1.0 · read-only preview', 174), ('license-badge.svg', 'license · Apache-2.0', 145)]:
    svg(filename, width, 22, label,
        f'<rect x=".5" y=".5" width="{width-1}" height="21" rx="4" fill="#15263b" stroke="#39516b"/>'
        + text(width/2, 15, label, 11, '#d3e6f4', 500, extra='text-anchor="middle"'))

capture = json.loads(CAPTURE.read_text())
scan, plan, apply = capture[1], capture[3], capture[6]
assert scan['argv'] == ['webpatch', 'scan'] and scan['exit'] == 2
assert plan['argv'] == ['webpatch', 'plan', '--dry-run'] and plan['exit'] == 4
assert apply['argv'] == ['webpatch', 'apply'] and apply['exit'] == 4
scan_lines = scan['stdout'].splitlines()
assessment = next(line for line in scan_lines if '"package": "php8.3-fpm:arm64"' in line)
plan_lines = plan['stdout'].splitlines()
# None marks an editorial omission, visibly separate from actual output.
sections = [
    ('webpatch scan', [scan_lines[0], scan_lines[1], None, assessment, None]),
    ('webpatch plan --dry-run', [plan_lines[0], None,
        next(line for line in plan_lines if '"CONTAINER_REBUILD_REQUIRED"' in line),
        next(line for line in plan_lines if '"REPAIR_EXECUTION_DISABLED"' in line), None]),
    ('webpatch apply', apply['stderr'].splitlines()),
]
for mobile in (False, True):
    w, size, margin = (400, 16, 20) if mobile else (1120, 17, 38)
    columns = int((w - 2 * margin) / (size * .61))
    body = text(margin, 34, 'WEBPATCH / CLI', 12, '#9ab3cc', 600, mono=True)
    body += text(w-margin, 34, 'UBUNTU 24.04 · ARM64', 10 if mobile else 12, '#9ab3cc', 500,
                 mono=True, extra='text-anchor="end"')
    body += f'<path d="M1 54H{w-1}" stroke="#263c52"/>'
    y = 89
    for command, lines in sections:
        body += text(margin, y, '$ ' + command, size, '#63dcea', 600, mono=True)
        y += 30
        for line in lines:
            if line is None:
                body += text(margin, y, '··· output omitted ···', size-3, '#8097af', mono=True)
                y += 23
                continue
            color = '#eab873' if ('UNKNOWN' in line or 'BLOCKED' in line or 'REQUIRED' in line or 'DISABLED' in line) else '#c5d3e5'
            if command == 'webpatch apply':
                color = '#f3a4a7'
            for wrapped in textwrap.wrap(line, columns, replace_whitespace=False, drop_whitespace=True, break_long_words=True, break_on_hyphens=False):
                body += text(margin, y, wrapped, size, color, mono=True, extra='xml:space="preserve"')
                y += 25
        y += 26
    body += f'<path d="M{margin} {y-4}H{w-margin}" stroke="#263c52"/>'
    body += text(margin, y+24, 'ACTUAL OUTPUT / SELECTED LINES / 2026-10-22', 10 if mobile else 12, '#9ab3cc', mono=True)
    h = y + 49
    svg('terminal-mobile.svg' if mobile else 'terminal.svg', w, h, 'WebPatch actual CLI output',
        f'<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="14" fill="#0b1525" stroke="#2d455e"/>' + body,
        'Real non-root container session. Runtime safety UNKNOWN. FPM version comparison only. Plan BLOCKED, APT dry-run NOT_RUN. Apply refuses. Omitted output is labeled; full capture is linked in the README.')

transcript = '# Actual CLI capture · Ubuntu 24.04 / arm64 · 2026-10-22\n# Non-root user 65534. No simulated or rewritten output.\n\n'
for command in (capture[0], scan, plan, apply):
    transcript += '$ ' + ' '.join(command['argv']) + '\n' + command['stdout']
    if command['stderr']:
        transcript += '# stderr\n' + command['stderr']
    transcript += '# exit: ' + str(command['exit']) + '\n\n'
(OUT / 'cli-transcript.txt').write_text(transcript.rstrip() + '\n')
print('Generated 9 static SVGs and the verbatim text transcript.')
