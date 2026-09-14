"""Build redistributable bundles from verified final wheels and explicit assets."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SDK = ROOT/'agent-comm-platform/agent-comm'
DOWNLOADS = ROOT/'downloads'
DOWNLOADS.mkdir(exist_ok=True)
WHEELS = [SDK/'python/dist/agent_comm_runtime-0.1.0-py3-none-any.whl',
          SDK/'connectors/hermes-platform/dist/hermes_platform_agent_comm-1.3.0-py3-none-any.whl']
SOURCES = [SDK/'python', SDK/'connectors/hermes-platform']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify_wheels():
    count = 0
    for wheel, source in zip(WHEELS, SOURCES):
        with zipfile.ZipFile(wheel) as z:
            for name in z.namelist():
                if '.dist-info/' in name or name.endswith('/'):
                    continue
                actual = source/name
                if not actual.is_file() or z.read(name) != actual.read_bytes():
                    raise RuntimeError('Wheel/source mismatch: '+name)
                count += 1
            package = 'agent_comm_runtime' if source.name == 'python' else 'hermes_platform_agent_comm'
            for item in (source/package).rglob('*'):
                if item.is_file() and item.suffix in {'.py','.yaml','.md'} and '__pycache__' not in item.parts:
                    if item.relative_to(source).as_posix() not in z.namelist():
                        raise RuntimeError('Missing packaged source: '+str(item))
    return count


def write_zip(path, files, executable=()):
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name, data in sorted(files.items()):
            info=zipfile.ZipInfo(name)
            info.date_time=(2026,9,14,0,0,0)
            info.compress_type=zipfile.ZIP_DEFLATED
            info.create_system=3
            info.external_attr=(0o100755 if name in executable else 0o100644)<<16
            z.writestr(info,data)


def source_files(repo):
    raw=subprocess.check_output(['git','-c','safe.directory='+repo.as_posix(),'ls-files','--cached','--others','--exclude-standard','-z'],cwd=repo)
    for name in sorted(set(raw.decode().split('\0'))):
        path=repo/name
        if not name or not path.is_file() or path.is_symlink():
            continue
        if any(p in {'build','dist','node_modules','.next','.git','.agents','.codex','__pycache__','downloads','output','tmp'} or p.endswith('.egg-info') for p in path.relative_to(repo).parts):
            continue
        if path.name.startswith('.env') or path.suffix in {'.db','.sqlite','.sqlite3','.log','.pem','.key','.exe','.pyc'}:
            continue
        data=path.read_bytes()
        # A developer's untracked, extensionless Go build is not source code.
        if data[:4] in {b'\x7fELF',b'\xcf\xfa\xed\xfe',b'\xfe\xed\xfa\xcf',b'\xca\xfe\xba\xbe'} or data[:2]==b'MZ':
            continue
        yield name,data


def main():
    verified=verify_wheels()
    common={name:(ROOT/'tools/early_access'/name).read_bytes() for name in ('README.md','install.py','configure_hermes.py')}
    common.update({'wheels/'+w.name:w.read_bytes() for w in WHEELS})
    variants={'windows-amd64':('agent-comm-helper.exe','agent-comm-helper.exe'),
              'linux-amd64':('agent-comm-helper-linux-amd64','agent-comm-helper'),
              'macos-arm64':('agent-comm-helper-darwin-arm64','agent-comm-helper')}
    outputs={}
    for platform,(binary,name) in variants.items():
        files={**common,name:(ROOT/'build/early-access'/binary).read_bytes()}
        files['SHA256SUMS.json']=json.dumps({'release':'2026-09-14','platform':platform,'files':{n:sha(b) for n,b in files.items()}},ensure_ascii=False,indent=2).encode()
        dest=DOWNLOADS/f'agent-comm-early-access-{platform}.zip'
        write_zip(dest,files,(name,))
        verifydir=ROOT/'build/early-access/verify-bundles'/platform
        verifydir.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(dest) as z:
            z.extractall(verifydir)
        subprocess.run([sys.executable,str(verifydir/'install.py'),'--check-only'],check=True)
        outputs[dest.name]={'bytes':dest.stat().st_size,'sha256':sha(dest.read_bytes())}
    # Preserve repository-relative documentation links in the developer source bundle.
    source={}
    for repo in (ROOT,ROOT/'agent-collaboration-web',ROOT/'agent-comm-platform',SDK):
        prefix=repo.relative_to(ROOT).as_posix()
        prefix='' if prefix=='.' else prefix+'/'
        for name,data in source_files(repo):
            source['agent-collaboration-deploy/'+prefix+name]=data
    sourcezip=DOWNLOADS/'agent-comm-early-access-source.zip'
    write_zip(sourcezip,source)
    outputs[sourcezip.name]={'bytes':sourcezip.stat().st_size,'sha256':sha(sourcezip.read_bytes())}
    pdf=ROOT/'output/pdf/agent-comm-early-access-invitation.pdf'
    (DOWNLOADS/pdf.name).write_bytes(pdf.read_bytes())
    outputs[pdf.name]={'bytes':pdf.stat().st_size,'sha256':sha(pdf.read_bytes())}
    report={'release':'2026-09-14','runtime':'0.1.0','hermes_connector':'1.3.0','verified_wheel_source_files':verified,'files':outputs}
    (DOWNLOADS/'release-manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
