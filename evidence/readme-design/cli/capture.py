import json, subprocess
from pathlib import Path
commands = [('--version',), ('scan',), ('scan','--format','json'), ('plan','--dry-run'), ('plan','--dry-run','--format','json'), ('verify-plan','/tmp/reviewed-plan.json','--format','json'), ('apply',)]
results=[]
for args in commands:
    r=subprocess.run(['webpatch',*args],capture_output=True,text=True)
    if args == ('plan','--dry-run','--format','json'):
        Path('/tmp/reviewed-plan.json').write_text(r.stdout)
    results.append({'argv':['webpatch',*args],'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
print(json.dumps(results,indent=2))
