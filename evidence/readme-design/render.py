import json, subprocess, re, posixpath
from pathlib import Path
root=Path.cwd()
(root/'build/readme-preview').mkdir(parents=True,exist_ok=True)
css='''body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}body{--bg:#fff;--fg:#1f2328;--muted:#59636e;--border:#d1d9e0;--code:#f6f8fa;--link:#0969da}@media(prefers-color-scheme:dark){body{--bg:#0d1117;--fg:#e6edf3;--muted:#9da7b3;--border:#3d444d;--code:#151b23;--link:#4493f8}}main{max-width:850px;margin:24px auto;padding:32px;border:1px solid var(--border);border-radius:6px}h1,h2{border-bottom:1px solid var(--border);padding-bottom:.3em;line-height:1.25}h1{font-size:2em}h2{font-size:1.5em;margin-top:24px}p,ul,table,pre{margin:0 0 16px}a{color:var(--link);text-decoration:none}img{max-width:100%;height:auto;vertical-align:middle}pre{padding:16px;background:var(--code);border-radius:6px;overflow:auto;font:13px/1.45 ui-monospace,SFMono-Regular,Consolas,monospace}code{padding:.2em .4em;border-radius:4px;background:var(--code);font-size:85%}pre code{padding:0;font-size:100%}table{display:block;max-width:100%;overflow:auto;border-collapse:collapse}td,th{padding:6px 13px;border:1px solid var(--border)}li+li{margin-top:.25em}.octicon{display:none}.anchor{display:none}.markdown-heading{position:relative}@media(max-width:600px){main{padding:16px;margin:0;border:0}h1{font-size:1.75em}h2{font-size:1.4em}}'''
for name in ('README.md','README.zh-CN.md','docs/cli.md','CONTRIBUTING.md','assets/readme/README.md'):
    p=root/name
    r=subprocess.run(['gh','api','markdown','--input','-'],input=json.dumps({'text':p.read_text(),'mode':'gfm'}),text=True,capture_output=True,check=True)
    fragment=r.stdout
    def local_url(m):
        key,url=m.group(1),m.group(2)
        if url.startswith(('http:', 'https:', '#')): return m.group(0)
        return key+'="/'+posixpath.normpath(str(p.parent.relative_to(root))+'/'+url)+'"'
    fragment=re.sub(r'<h([1-6])>(.*?)</h\1>', lambda m: '<h'+m[1]+' id="'+re.sub(r'[^\w\- ]','',m[2].lower()).replace(' ','-')+'">'+m[2]+'</h'+m[1]+'>', fragment)
    fragment=re.sub(r'(href|src|srcset)="([^"]+)"',local_url,fragment).replace('id="user-content-','id="')
    slug=name.replace('/','-').replace('.md','.html')
    (root/'build/readme-preview'/slug).write_text('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+name+'</title><style>'+css+'</style></head><body><main class="markdown-body">'+fragment+'</main></body></html>')
    (root/'build/readme-preview'/(slug+'.fragment')).write_text(r.stdout)
    if name.startswith('README'):
        light=(root/'build/readme-preview'/slug).read_text()
        dark=light.replace('<style>', '<style>body{--bg:#0d1117!important;--fg:#e6edf3!important;--muted:#9da7b3!important;--border:#3d444d!important;--code:#151b23!important;--link:#4493f8!important}')
        dark=dark.replace('(prefers-color-scheme: dark)', '(min-width: 0px)').replace('hero-mobile-light.svg','hero-mobile-dark.svg').replace('hero-light.svg','hero-dark.svg')
        (root/'build/readme-preview'/('dark-'+slug)).write_text(dark)
    print('PASS GitHub GFM render:',name)
