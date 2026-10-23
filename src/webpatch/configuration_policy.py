"""Reviewed PHP2Shell configuration delta; never patch proof or a config writer."""
DIRECTIVE='memory_hard_limit_percent'
REFERENCE='https://raw.githubusercontent.com/php/php-src/php-8.3.36/main/main.c'
CONFIG_FIELDS=('ini_file','ini_scanned','effective_ini_sha256','effective_ini_baseline_sha256',
               'extensions_sha256','reviewed_directives')
POLICY={'revision':'php2shell-ini-addition-v1','allowed_new_directive':DIRECTIVE,
        'allowed_new_state':'VENDOR_DEFAULT','reference':REFERENCE,
        'requirement':'Every other effective INI value, input path and loaded extension name must remain unchanged.'}


def validate_directive_observation(value):
    if not isinstance(value,dict) or set(value)!={DIRECTIVE}: return False
    item=value[DIRECTIVE]
    if not isinstance(item,dict): return False
    if item=={'state':'ABSENT'} or item=={'state':'VENDOR_DEFAULT'}: return True
    return (set(item)=={'state','value'} and item['state']=='EXPLICIT_VALUE'
            and isinstance(item['value'],str) and item['value'].isascii() and item['value'].isdigit()
            and 3<=len(item['value'])<=10 and int(item['value'])>=100)


def configuration_transition(before,after):
    if (not validate_directive_observation(before.get('reviewed_directives'))
            or not validate_directive_observation(after.get('reviewed_directives'))): return 'UNKNOWN'
    if any(before.get(k)!=after.get(k) for k in ('ini_file','ini_scanned','extensions_sha256','effective_ini_baseline_sha256')):
        return 'UNKNOWN'
    old,new=before['reviewed_directives'][DIRECTIVE],after['reviewed_directives'][DIRECTIVE]
    if before['effective_ini_sha256']==after['effective_ini_sha256'] and old==new: return 'UNCHANGED'
    if (old=={'state':'ABSENT'} and new=={'state':'VENDOR_DEFAULT'}
            and before['effective_ini_sha256']==before['effective_ini_baseline_sha256']
            and after['effective_ini_sha256']!=after['effective_ini_baseline_sha256']):
        return 'REVIEWED_VENDOR_DIRECTIVE_ADDED'
    return 'UNKNOWN'
