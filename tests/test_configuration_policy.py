from copy import deepcopy

import pytest

from webpatch.configuration_policy import DIRECTIVE,MULTIPART,DIRECTIVES,configuration_transition,validate_directive_observation


def original():
    return {'ini_file':'/etc/php/8.3/fpm/php.ini','ini_scanned':[],
        'effective_ini_sha256':'a'*64,'effective_ini_baseline_sha256':'a'*64,'extensions_sha256':'b'*64,
        'reviewed_directives':{name:{'state':'ABSENT'} for name in DIRECTIVES}}


def patched():
    value=original();value['effective_ini_sha256']='c'*64
    value['reviewed_directives'][DIRECTIVE]={'state':'VENDOR_DEFAULT'}
    return value


def test_only_the_reviewed_new_default_can_explain_a_changed_aggregate():
    assert configuration_transition(original(),original())=='UNCHANGED'
    assert configuration_transition(original(),patched())=='REVIEWED_VENDOR_DIRECTIVES_ADDED'
    assert configuration_transition(patched(),patched())=='UNCHANGED'


@pytest.mark.parametrize('change',['other-setting','input-path','extensions','nondefault-new','removed','malformed'])
def test_unreviewed_configuration_changes_remain_unknown(change):
    before,after=original(),patched()
    if change=='other-setting': after['effective_ini_baseline_sha256']='f'*64
    elif change=='input-path': after['ini_scanned']=['/etc/php/8.3/fpm/conf.d/new.ini']
    elif change=='extensions': after['extensions_sha256']='f'*64
    elif change=='nondefault-new': after['reviewed_directives'][DIRECTIVE]={'state':'EXPLICIT_VALUE','value':'300'}
    elif change=='removed': before,after=patched(),original()
    elif change=='malformed': after['reviewed_directives'][DIRECTIVE]={'state':'VENDOR_DEFAULT','approved':True}
    assert configuration_transition(before,after)=='UNKNOWN'


def test_existing_explicit_value_must_stay_identical():
    before=patched();before['reviewed_directives'][DIRECTIVE]={'state':'EXPLICIT_VALUE','value':'200'}
    assert configuration_transition(before,deepcopy(before))=='UNCHANGED'
    after=deepcopy(before);after['reviewed_directives'][DIRECTIVE]['value']='300';after['effective_ini_sha256']='d'*64
    assert configuration_transition(before,after)=='UNKNOWN'


@pytest.mark.parametrize('value',['-2','0','99','100000000000','secret','２００',200])
def test_unclassified_or_non_numeric_directive_values_do_not_enter_receipts(value):
    assert not validate_directive_observation({DIRECTIVE:{'state':'EXPLICIT_VALUE','value':value},MULTIPART:{'state':'ABSENT'}})


def test_each_reviewed_addition_can_arrive_alone_or_together_but_not_change_an_existing_value():
    for names in ((MULTIPART,),DIRECTIVES):
        after=original();after['effective_ini_sha256']='d'*64
        for name in names: after['reviewed_directives'][name]={'state':'VENDOR_DEFAULT'}
        assert configuration_transition(original(),after)=='REVIEWED_VENDOR_DIRECTIVES_ADDED'
    before=patched();before['reviewed_directives'][MULTIPART]={'state':'EXPLICIT_VALUE','value':'1200'}
    after=deepcopy(before);after['effective_ini_sha256']='f'*64
    after['reviewed_directives'][MULTIPART]={'state':'EXPLICIT_VALUE','value':'1300'}
    assert configuration_transition(before,after)=='UNKNOWN'
