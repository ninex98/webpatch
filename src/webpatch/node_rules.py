"""Node RuleProvider: vendor source-package versions, separate from PHP rules."""
from collections import Counter
from datetime import datetime
import hashlib
from importlib.resources import files
import json
import re

from .models import Assessment
from .system import VERSION


class NodeRuleProvider:
    def __init__(self,raw=None):
        raw=raw if raw is not None else files('webpatch').joinpath('data/nodejs.json').read_bytes()
        self.data=json.loads(raw); self.sha256=hashlib.sha256(raw).hexdigest()
        self.revision=self.data['revision']
        self.reviewed=datetime.fromisoformat(self.data['reviewed_at'])
        self.expires=datetime.fromisoformat(self.data['valid_until'])
        if (self.data['schema_version']!=1 or not self.reviewed.tzinfo or not self.expires.tzinfo
                or self.reviewed>=self.expires or len(set(self.data['cves']))!=len(self.data['cves'])):
            raise ValueError('NODE_RULE_SCHEMA_OR_VALIDITY_INVALID')
        keys=[]
        for row in self.data['rules']:
            keys.append(tuple(row[k] for k in ('os_id','version_id','codename','source_name')))
            re.compile(row['version_pattern'])
            for cve in self.data['cves']:
                if not VERSION.fullmatch(row['fixes'][cve]) or not row['references'][cve]:
                    raise ValueError('NODE_RULE_BOUNDARY_INVALID')
        if len(keys)!=len(set(keys)): raise ValueError('NODE_RULE_AMBIGUOUS')

    def assess(self,inventory,comparator,now):
        if not now.tzinfo: raise ValueError('TIMEZONE_REQUIRED')
        rows=[]; counts=Counter(p.id for p in inventory.packages)
        env=inventory.environment
        for package in inventory.packages:
            if package.sapi!='node': continue
            rule=next((r for r in self.data['rules'] if (r['os_id'],r['version_id'],r['codename'],r['source_name'])
                       ==(env.os_id,env.version_id,env.codename,package.source_name)),None)
            for cve in self.data['cves']:
                status='UNKNOWN'; evidence=(package.evidence_id,)
                fixed=rule['fixes'][cve] if rule else None
                refs=tuple(rule['references'][cve]) if rule else ('https://security-tracker.debian.org/tracker/'+cve,)
                if not self.reviewed<=now<self.expires: reason='NODE_RULES_EXPIRED_OR_CLOCK_BEFORE_REVIEW'
                elif counts[package.id]!=1: reason='NODE_PACKAGE_ID_AMBIGUOUS'
                elif package.status not in {'install ok installed','hold ok installed'}: reason='NODE_PACKAGE_NOT_CONFIGURED'
                elif not rule: reason='NODE_VENDOR_RELEASE_SOURCE_RULE_UNAVAILABLE'
                elif (package.name.split(':')[0]!='nodejs' or not re.fullmatch(r'[a-z0-9][a-z0-9-]*',package.architecture)
                      or (':' in package.name and package.name.split(':')[1]!=package.architecture)
                      or not re.fullmatch(re.escape(package.source_version)+r'(?:\+b[0-9]+)?',package.version)):
                    reason='NODE_PACKAGE_IDENTITY_INCONSISTENT'
                elif not re.fullmatch(rule['version_pattern'],package.source_version): reason='NODE_VENDOR_VERSION_FAMILY_UNKNOWN'
                else:
                    meets,ident=comparator.at_least(package.source_version,fixed); evidence+=(ident,)
                    status='UNKNOWN' if meets is None else 'MEETS_VENDOR_FIX' if meets else 'BELOW_VENDOR_FIX'
                    reason='NODE_COMPARISON_FAILED' if meets is None else 'VERSION_ONLY_ORIGIN_AND_RUNNING_CODE_UNVERIFIED'
                rows.append(Assessment(package.id,cve,status,reason,fixed,refs,evidence))
        return rows
