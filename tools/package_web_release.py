"""Snapshot the current Web source and deployment config without private data."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / 'agent-collaboration-web'
OUT = ROOT / 'build/early-access/web-release.tar.gz'
OUT.parent.mkdir(parents=True, exist_ok=True)
TEXT = {'.ts', '.tsx', '.js', '.cjs', '.mjs', '.json', '.md', '.prisma', '.sql', '.sh', '.css', '.yaml', '.yml', '.html', '.txt'}
names = subprocess.check_output(['git', '-c', 'safe.directory='+WEB.as_posix(), 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=WEB).decode().split('\0')
files = {}
for name in sorted(set(filter(None, names))):
    path = WEB / name
    if not path.is_file() or path.is_symlink() or any(p in {'build', 'node_modules', '.git', '.next', '.codex', '.agents'} for p in path.relative_to(WEB).parts):
        continue
    if path.name.startswith('.env') or path.suffix in {'.db', '.sqlite', '.sqlite3', '.log', '.key', '.pem'}:
        continue
    data = path.read_bytes()
    if path.suffix in TEXT or path.name.startswith('.') or path.name == 'Dockerfile':
        data = data.replace(b'\r\n', b'\n')
    files['web/'+name] = data
for name in ('docker-compose.yml', 'nginx.conf'):
    files[name] = (ROOT/name).read_bytes().replace(b'\r\n', b'\n')
deleted = subprocess.check_output(['git', '-c', 'safe.directory='+WEB.as_posix(), 'diff', '--name-only', '--diff-filter=D'], cwd=WEB).decode().splitlines()
backup_manifest = WEB / 'build/retired-web-source-20260914/manifest.json'
manifest = {'release':'early-access-20260914', 'files': {n: hashlib.sha256(b).hexdigest() for n,b in files.items()},
            'remove_web': deleted, 'source_head': subprocess.check_output(['git','-c','safe.directory='+WEB.as_posix(),'rev-parse','HEAD'],cwd=WEB).decode().strip()}
files['manifest.json'] = json.dumps(manifest, indent=2).encode()
with tarfile.open(OUT, 'w:gz') as archive:
    for name, data in files.items():
        info = tarfile.TarInfo(name)
        info.size = len(data)
        info.mode = 0o755 if name.endswith('.sh') else 0o644
        archive.addfile(info, io.BytesIO(data))
print(json.dumps({'archive':str(OUT),'files':len(files),'bytes':OUT.stat().st_size,'sha256':hashlib.sha256(OUT.read_bytes()).hexdigest()}))
