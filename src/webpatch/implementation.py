"""Bind review receipts to all shipped implementation and rule resources."""
import hashlib
from importlib.resources import files
import json


def implementation_sha256():
    hashes={}
    def visit(directory,prefix=''):
        for entry in directory.iterdir():
            if entry.name.startswith('.') or entry.name=='__pycache__': continue
            name=prefix+entry.name
            if entry.is_dir(): visit(entry,name+'/')
            elif entry.name.endswith(('.py','.php','.json')):
                hashes[name]=hashlib.sha256(entry.read_bytes()).hexdigest()
                if len(hashes)>128: raise ValueError('IMPLEMENTATION_PACKAGE_LIMIT')
    visit(files('webpatch'))
    return hashlib.sha256(json.dumps(hashes,sort_keys=True,separators=(',',':')).encode()).hexdigest()
