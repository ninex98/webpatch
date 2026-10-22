import pytest

from webpatch.implementation import implementation_sha256
from webpatch.system import LocalSystem,ProbeError
from webpatch.cli import main


def test_receipts_bind_runtime_helpers_and_rule_resources_not_an_incomplete_file_list(monkeypatch,tmp_path):
    (tmp_path/'runtime.py').write_text('version=1\n')
    (tmp_path/'data').mkdir()
    (tmp_path/'data/rules.json').write_text('{}')
    monkeypatch.setattr('webpatch.implementation.files',lambda package:tmp_path)
    original=implementation_sha256()
    (tmp_path/'runtime.py').write_text('version=2\n')
    changed=implementation_sha256()
    assert changed!=original
    (tmp_path/'data/rules.json').write_text('{"new":true}')
    assert implementation_sha256()!=changed


@pytest.mark.parametrize('pid',['../1','1/fd',1])
def test_descriptor_reader_rejects_non_pid_inputs_before_io(pid,monkeypatch):
    monkeypatch.setattr('webpatch.system.os.scandir',lambda *args:pytest.fail('unexpected filesystem read'))
    with pytest.raises(ProbeError,match='DESCRIPTOR_PROCESS_ID_INVALID'):
        LocalSystem().file_descriptors(pid)


def test_injected_local_subclass_does_not_implicitly_get_native_mutation_capabilities(monkeypatch,capsys):
    class InjectedLocal(LocalSystem):
        def read_plan_document(self,path): return '{"state_directory":"/var/lib/webpatch"}'
    monkeypatch.setattr('webpatch.cli.LocalServiceControl',lambda *args:pytest.fail('native capability fallback'))
    result=main(['prepare-scope','/fixture.json','--confirm-sha256','a'*64],system=InjectedLocal())
    assert result==3 and 'ERROR' in capsys.readouterr().err
