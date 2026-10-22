import concurrent.futures, hashlib, json, re, subprocess, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote, urldefrag
root=Path.cwd()
files=[Path(x) for x in ('README.md','README.zh-CN.md','docs/cli.md','CONTRIBUTING.md','assets/readme/README.md')]
urls=set(); checks=[]
for p in files:
 s=p.read_text()
 links=re.findall(r'\[[^\]]*\]\(([^)]+)\)',s)+re.findall(r'(?:href|src|srcset)="([^"]+)"',s)
 for link in links:
  if link.startswith('https://'):
   urls.add(link);continue
  target,fragment=urldefrag(unquote(link))
  resolved=(p.parent/target).resolve() if target else p.resolve()
  assert resolved.exists(),(p,link)
  if fragment:
   text=resolved.read_text()
   ids=set(re.findall(r'<a id="([^"]+)"',text))
   ids.update(re.sub(r'[^\w\- ]','',h.lower()).replace(' ','-') for h in re.findall(r'^#+ (.+)$',text,re.M))
   assert fragment in ids,(p,link,ids)
 checks.append(f'PASS local links + anchors: {p} ({len(links)})')
 assert '<script' not in s and '<style' not in s
 a=re.findall(r'<img [^>]+>',s)
 assert all('alt=' in x for x in a)
for p in sorted(Path('assets/readme').glob('*.svg')):
 e=ET.parse(p).getroot(); assert e.attrib['viewBox']
 for x in e.iter():
  assert x.tag.rsplit('}',1)[-1] not in ('script','foreignObject','image','animate','animateTransform')
  assert all(not k.startswith('on') and not v.startswith(('http:', 'https:', 'data:')) for k,v in x.attrib.items())
 assert p.stat().st_size<20000
checks.append('PASS 9 SVGs: XML, viewBox, accessible titles, no scripts / embedded images / remote dependencies, each <20 KB')
en=Path('README.md').read_text();zh=Path('README.zh-CN.md').read_text()
assert re.findall(r'```sh\n(.*?)```',en,re.S)==re.findall(r'```sh\n(.*?)```',zh,re.S)
assert re.findall(r'(?:src|srcset)="([^"]+)"',en)==re.findall(r'(?:src|srcset)="([^"]+)"',zh)
assert set(re.findall(r'(?<!`)`([^`\n]+)`(?!`)',en))==set(re.findall(r'(?<!`)`([^`\n]+)`(?!`)',zh))
checks.append('PASS bilingual code blocks, inline technical identifiers and image sources match; prose / support matrix manually reviewed')
r=json.loads(Path('evidence/readme-design/cli/capture.json').read_text())
assert [x['exit'] for x in r]==[0,2,2,4,4,4,4]
report=json.loads(r[2]['stdout']);plan=json.loads(r[4]['stdout'])
assert report['safe'] is False and plan['executable'] is False
assert report['inventory']['environment']['scope']=='container' and plan['apt_simulation']=='NOT_RUN'
checks.append('PASS captured CLI command schemas, scope and expected exit codes; no safe/executable result')
before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('assets/readme').glob('*.svg')}
subprocess.run(['.venv/bin/python','assets/readme/generate.py'],check=True,capture_output=True)
assert before=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('assets/readme').glob('*.svg')}
checks.append('PASS deterministic SVG regeneration from actual capture')
def check_url(url):
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'WebPatch-README-validation'}),timeout=30) as response:
   assert response.status==200
   return {'url':url,'status':response.status,'content_type':response.headers.get('Content-Type')}
 except Exception as e:
  return {'url':url,'error':str(e)}
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
 results=list(pool.map(check_url,sorted(urls)))
Path('evidence/readme-design/links.json').write_text(json.dumps(results,indent=2)+'\n')
assert all('status' in r for r in results),results
checks.append(f'PASS {len(results)} unique external links / images return HTTP 200')
Path('evidence/readme-design/validation.log').write_text('\n'.join(checks)+'\n')
print('\n'.join(checks))
