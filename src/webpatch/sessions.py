"""Explicit private output capability for guided maintenance; scans never use it."""
import json
import os
from pathlib import Path
import re
import secrets
import stat


class SessionStore:
    def __init__(self, state_directory):
        if not re.fullmatch(r'/var/lib/webpatch(?:-[a-z0-9-]+)?', str(state_directory)):
            raise ValueError('SESSION_STATE_DIRECTORY_INVALID')
        self.root = Path(state_directory)
        self.path = None

    @staticmethod
    def directory(path):
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        info = os.fstat(descriptor)
        if info.st_uid != os.geteuid() or info.st_mode & 0o077:
            os.close(descriptor)
            raise ValueError('SESSION_DIRECTORY_UNTRUSTED')
        return descriptor

    def create(self):
        if os.geteuid() != 0:
            raise ValueError('SESSION_REQUIRES_ROOT')
        self.root.mkdir(mode=0o700, exist_ok=True)
        descriptor = self.directory(self.root)
        try:
            name = 'session-' + secrets.token_hex(12)
            os.mkdir(name, mode=0o700, dir_fd=descriptor)
            os.fsync(descriptor)
            self.path = self.root / name
        finally:
            os.close(descriptor)
        return self

    def write(self, name, document):
        if self.path is None or name not in {'preparation.json', 'preparation-result.json', 'startup.json', 'review.json', 'result.json'}:
            raise ValueError('SESSION_DOCUMENT_INVALID')
        payload = (json.dumps(document, ensure_ascii=True, indent=2) + '\n').encode()
        if len(payload) > 16 * 1024 * 1024:
            raise ValueError('SESSION_DOCUMENT_LIMIT')
        parent = self.directory(self.path)
        try:
            descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(payload); stream.flush(); os.fsync(stream.fileno())
            os.fsync(parent)
        finally:
            os.close(parent)
        return str(self.path / name)
