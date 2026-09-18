"""Read-only public-file allowlist/hash and common credential-pattern checks.

This catches accidental changes; it is not a comprehensive secret scanner or
an authorization check. Review every new manifest entry before publication.
"""
import argparse
import hashlib
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'PUBLIC_FILES.sha256'
PATTERNS = [
    rb'gh[pousr]_[A-Za-z0-9]{20,}',
    rb'github_pat_[A-Za-z0-9_]{20,}',
    rb'(?i)dapi[0-9a-f]{24,}',
    rb'AKIA[A-Z0-9]{16}',
    rb'-----BEGIN [A-Z ]*PRIVATE KEY-----',
    rb'/Users/[A-Za-z0-9_.-]+/',
    rb'https://[A-Za-z0-9.-]+\.(?:cloud|azuredatabricks)\.databricks\.com',
    rb'https://adb-[A-Za-z0-9.-]+\.azuredatabricks\.net',
]


def check(staged=False):
    def content(path):
        if staged:
            return subprocess.check_output(['git', 'show', ':' + path], cwd=ROOT)
        return (ROOT / path).read_bytes()

    manifest = content(MANIFEST).decode('utf-8')
    entries = {}
    for line in manifest.splitlines():
        digest, path = line.split('  ', 1)
        relative = Path(path)
        assert re.fullmatch(r'[a-f0-9]{64}', digest), 'Invalid checksum'
        assert not relative.is_absolute() and '..' not in relative.parts, 'Invalid path'
        assert path not in entries and path != MANIFEST, 'Duplicate or self-referencing entry'
        entries[path] = digest
    assert entries, 'Empty publication allowlist'
    for path, expected in entries.items():
        assert (ROOT / path).resolve().is_relative_to(ROOT.resolve()), 'Symlink leaves snapshot'
        raw = content(path)
        assert len(raw) < 250_000, f'Unexpected large public file: {path}'
        assert hashlib.sha256(raw).hexdigest() == expected, f'Changed unreviewed file: {path}'
        raw.decode('utf-8')
        for pattern in PATTERNS:
            assert not re.search(pattern, raw), f'Potential private content in {path}'
    tracked = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, capture_output=True, check=False)
    if tracked.returncode == 0:
        paths = set(tracked.stdout.decode().rstrip('\0').split('\0')) - {''}
        assert paths == set(entries) | {MANIFEST}, 'Tracked files differ from reviewed public allowlist'
    elif staged:
        raise RuntimeError('Staged check requires a Git repository')
    print(f'PASS: {len(entries)} allowlisted files; hashes and common credential-pattern checks')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--staged', action='store_true')
    check(parser.parse_args().staged)
