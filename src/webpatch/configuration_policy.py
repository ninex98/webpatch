"""Reviewed PHP2Shell configuration delta; never patch proof or a config writer."""
DIRECTIVE='memory_hard_limit_percent'
MULTIPART='max_multipart_body_parts'
DIRECTIVES=(DIRECTIVE,MULTIPART)
REFERENCE='https://raw.githubusercontent.com/php/php-src/php-8.3.36/main/main.c'
CONFIG_FIELDS=('ini_file','ini_scanned','effective_ini_sha256','effective_ini_baseline_sha256',
               'extensions_sha256','reviewed_directives')
POLICY={'revision':'php-maintenance-ini-additions-v2','allowed_new_directives':DIRECTIVES,
        'allowed_new_state':'VENDOR_DEFAULT','references':(REFERENCE,'https://raw.githubusercontent.com/php/php-src/php-8.1.33/main/main.c'),
        'requirement':'Every other effective INI value, input path and loaded extension name must remain unchanged.'}


def validate_directive_observation(value):
    if not isinstance(value,dict) or set(value)!=set(DIRECTIVES): return False
    for name,item in value.items():
        if not isinstance(item,dict): return False
        if item=={'state':'ABSENT'} or item=={'state':'VENDOR_DEFAULT'}: continue
        if not (set(item)=={'state','value'} and item['state']=='EXPLICIT_VALUE'
                and isinstance(item['value'],str) and item['value'].isascii() and item['value'].isdigit()
                and 1<=len(item['value'])<=10 and int(item['value'])>=(100 if name==DIRECTIVE else 0)):
            return False
    return True


def configuration_transition(before,after):
    if (not validate_directive_observation(before.get('reviewed_directives'))
            or not validate_directive_observation(after.get('reviewed_directives'))): return 'UNKNOWN'
    if any(before.get(k)!=after.get(k) for k in ('ini_file','ini_scanned','extensions_sha256','effective_ini_baseline_sha256')):
        return 'UNKNOWN'
    old,new=before['reviewed_directives'],after['reviewed_directives']
    if before['effective_ini_sha256']==after['effective_ini_sha256'] and old==new: return 'UNCHANGED'
    changed=[name for name in DIRECTIVES if old[name]!=new[name]]
    if (changed and all(old[name]=={'state':'ABSENT'} and new[name]=={'state':'VENDOR_DEFAULT'} for name in changed)
            and after['effective_ini_sha256']!=after['effective_ini_baseline_sha256']):
        return 'REVIEWED_VENDOR_DIRECTIVES_ADDED'
    return 'UNKNOWN'
