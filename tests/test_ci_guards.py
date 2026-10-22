import os
from pathlib import Path
import subprocess
import sys


def test_destructive_debian_harnesses_refuse_non_hosted_context_before_setup(tmp_path):
    repository=Path(__file__).resolve().parents[1]
    env={**os.environ,'GITHUB_ACTIONS':'false','RUNNER_ENVIRONMENT':'local','RUNNER_TEMP':str(tmp_path)}
    for command in ([sys.executable,str(repository/'scripts/ci_debian_vm.py'),'12','fpm'],
                    ['bash',str(repository/'scripts/ci_debian_guest.sh'),'fpm']):
        result=subprocess.run(command,cwd=tmp_path,env=env,capture_output=True,text=True,timeout=10)
        assert result.returncode!=0
    assert not list(tmp_path.iterdir())
