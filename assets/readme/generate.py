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
CAPTURE = ROOT / 'evidence/phase-6b-guided/terminal-capture.json'
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
            body += text(32, 268, 'READ-ONLY SCANS / CONFIRMED MAINTENANCE', 11, muted, 500, mono=True)
        else:
            body += '<defs><pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse"><path d="M32 0H0V32" fill="none" stroke="' + line + '" stroke-width=".6"/></pattern></defs>'
            body += '<rect x="710" y="1" width="409" height="348" rx="18" fill="url(#grid)" opacity=".45"/>'
            body += mark(42, 53, .8, accent)
            body += text(127, 109, 'WebPatch', 57, ink, 650, extra='letter-spacing="-2"')
            body += text(48, 177, 'Evidence before action.', 38, ink, 550, extra='letter-spacing="-.7"')
            body += text(48, 218, 'PHP runtime security, grounded in evidence.', 21, muted)
            body += f'<path d="M48 263H653" stroke="{line}"/>'
            body += text(48, 300, 'READ-ONLY SCANS', 12, accent, 600, extra='letter-spacing="2"')
            body += text(313, 300, 'DISCOVER / ASSESS / REVIEW', 12, muted, 500, mono=True)
            for i, (label, sub) in enumerate((('Local evidence', 'Packages / processes / services'), ('Vendor context', 'Distribution-aware assessments'), ('Reviewable plans', 'Exact review and confirmation'))):
                y = 51 + i * 88
                body += f'<rect x="750" y="{y}" width="322" height="71" rx="8" fill="{bg}" stroke="{line}"/>'
                body += text(767, y+30, f'0{i+1}', 13, accent, 600, mono=True)
                body += text(804, y+30, label, 18, ink, 550)
                body += text(804, y+53, sub, 12, muted)
                if i < 2:
                    body += f'<path d="M783 {y+71}v17" stroke="{accent}" stroke-width="2"/>'
        svg(f'hero-{"mobile-" if mobile else ""}{theme}.svg', w, h,
            'WebPatch — Evidence before action.', body,
            'Read-only PHP runtime security inventory. Discover local evidence, assess vendor context, review plans. Exact review and confirmation.')

for filename, label, width in [('preview-badge.svg', '0.2.0 · Linux preview', 174), ('license-badge.svg', 'license · Apache-2.0', 145)]:
    svg(filename, width, 22, label,
        f'<rect x=".5" y=".5" width="{width-1}" height="21" rx="4" fill="#15263b" stroke="#39516b"/>'
        + text(width/2, 15, label, 11, '#d3e6f4', 500, extra='text-anchor="middle"'))

capture = json.loads(CAPTURE.read_text())
assert capture['version'] == '0.2.0' and capture['uid'] == 65534
transcript = []
for record in capture['records']:
    assert record['exit'] == 2 and 'UNKNOWN' in record['stdout'] and not record['stderr']
    assert record['argv'] == ['webpatch', 'scan', '--color', 'never', '--lang', 'en']
    mobile = record['columns'] == 44
    w, size, step, margin = (480, 14, 22, 20) if mobile else (1120, 18, 28, 36)
    lines = record['stdout'].strip('\n').splitlines()
    h = 112 + len(lines) * step
    body = f'<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="14" fill="#0b1525" stroke="#2d455e"/>'
    body += text(margin, 31, 'WEBPATCH / ACTUAL CLI', 12, '#9ab3cc', 600, mono=True)
    body += f'<path d="M1 48H{w-1}" stroke="#263c52"/>'
    for i, line in enumerate(lines):
        stripped = line.strip()
        color = '#eab873' if stripped.startswith('UNKNOWN') else '#c5d3e5'
        weight = 400
        if stripped.startswith('WebPatch') or stripped == 'webpatch scan --details':
            color = '#63dcea'; weight = 600
        elif stripped in {'Result', 'What still needs checking', 'Next step'}:
            color = '#f0f6fc'; weight = 600
        elif stripped.startswith(('─', 'Ubuntu', 'Read-only', 'Rules valid')):
            color = '#8097af'
        body += text(margin, 82+i*step, line, size, color, weight, mono=True, extra='xml:space="preserve"')
    body += text(margin, h-15, 'UBUNTU 24.04 · ARM64 · 2026-10-23', 11, '#9ab3cc', mono=True)
    svg('terminal-mobile.svg' if mobile else 'terminal.svg',w,h,'WebPatch readable CLI output',body,
        'Complete actual installed CLI output. Empty inventory stays UNKNOWN. No JSON wall or synthetic diagnosis.')
    transcript.append(f"# {record['columns']} columns / exit {record['exit']}\n" + record['stdout'])
(OUT/'cli-transcript.txt').write_text('\n'.join(transcript).rstrip() + '\n')
