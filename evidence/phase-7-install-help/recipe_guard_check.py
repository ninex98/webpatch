
import json,os,pathlib,subprocess,sys,tempfile
recipes=json.load(sys.stdin)
results=[]
with tempfile.TemporaryDirectory() as folder:
 root=pathlib.Path(folder);binary=root/'bin';binary.mkdir()
 curl=binary/'curl'
 curl.write_text(r"""#!/usr/bin/python3
import os,pathlib,sys
args=sys.argv[1:]
assert '--retry-all-errors' in args and '--retry' in args
assert args[args.index('--proto')+1]=='=https'
assert args[args.index('--proto-redir')+1]=='=https'
out=pathlib.Path(args[args.index('-o')+1])
if os.environ['WP_TEST_CASE']=='partial':
 out.write_text('echo EXECUTED > "$WP_TEST_EXECUTED"' + chr(10))
 print('curl: (56) simulated interrupted receive',file=sys.stderr)
 sys.exit(56)
out.write_bytes(b'corrupted package bytes')
""")
 curl.chmod(0o755)
 apt=binary/'apt-get';apt.write_text(chr(10).join(['#!/bin/sh','echo APT > "$WP_TEST_EXECUTED"','exit 99','']));apt.chmod(0o755)
 for name,case in [('bootstrap','partial'),('direct-package','partial'),('direct-package','corrupt')]:
  marker=root/'unexpected-execution'
  recipe=root/'recipe.sh';recipe.write_text(recipes[name])
  env=dict(os.environ,PATH=str(binary)+':'+os.environ['PATH'],WP_TEST_CASE=case,WP_TEST_EXECUTED=str(marker))
  result=subprocess.run(['sh',str(recipe)],capture_output=True,text=True,env=env)
  assert result.returncode!=0 and not marker.exists(),(name,case,result.stdout,result.stderr)
  if case=='partial':assert result.returncode==56,(result.returncode,result.stderr)
  results.append({'recipe':name,'case':case,'result':'PASS','exit_code':result.returncode,'executed':False,'stderr':result.stderr})
print(json.dumps(results,indent=2))
