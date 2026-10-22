"""Local collector receipts. The key never appears in JSON or audit output."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import stat


class ReceiptStore:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.key_path = self.directory / 'collector.key'

    def _key(self, create=False):
        if create:
            self.directory.mkdir(mode=0o700, parents=False, exist_ok=True)
        info = self.directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise ValueError('RECEIPT_DIRECTORY_UNTRUSTED')
        if create:
            try:
                descriptor = os.open(self.key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os,'O_NOFOLLOW',0), 0o600)
            except FileExistsError:
                pass
            else:
                try:
                    raw = secrets.token_bytes(64)
                    offset = 0
                    while offset < len(raw): offset += os.write(descriptor, raw[offset:])
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        descriptor = os.open(self.key_path, os.O_RDONLY | getattr(os,'O_NOFOLLOW',0) | os.O_NONBLOCK)
        with os.fdopen(descriptor,'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077 or info.st_size != 64:
                raise ValueError('RECEIPT_KEY_UNTRUSTED')
            return stream.read(65)

    @staticmethod
    def _bytes(payload):
        return json.dumps(payload,sort_keys=True,separators=(',',':')).encode()

    def seal(self, payload):
        raw = self._bytes(payload)
        if len(raw) > 1024*1024: raise ValueError('RECEIPT_PAYLOAD_LIMIT')
        return {'schema_version':1, 'payload':payload,
                'hmac_sha256':hmac.new(self._key(create=True), raw, hashlib.sha256).hexdigest()}

    def verify(self, document):
        if not isinstance(document,dict) or set(document) != {'schema_version','payload','hmac_sha256'} or type(document['schema_version']) is not int or document['schema_version'] != 1:
            raise ValueError('RECEIPT_SCHEMA_INVALID')
        raw = self._bytes(document['payload'])
        if len(raw) > 1024*1024 or not isinstance(document['hmac_sha256'],str):
            raise ValueError('RECEIPT_PAYLOAD_INVALID')
        expected = hmac.new(self._key(),raw,hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected,document['hmac_sha256']):
            raise ValueError('RECEIPT_AUTHENTICATION_FAILED')
        return document['payload']
