"""Verify or restore project skills without executing downloaded code.

python tools/manage_skills.py --verify
python tools/manage_skills.py --install
Existing modified skill directories are never overwritten.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def verify(directory, expected):
    if not directory.is_dir(): return False
    actual = {}
    for path in directory.rglob('*'):
        if path.is_symlink(): return False
        if path.is_file(): actual[path.relative_to(directory).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return actual == expected

def run_git(*args):
    subprocess.run(['git','-c','core.hooksPath=/dev/null',*args], check=True, stdout=subprocess.DEVNULL)

def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--install', action='store_true')
    mode.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    lock = json.loads((ROOT/'skills.lock.json').read_text())
    target = ROOT/lock['destination']
    with tempfile.TemporaryDirectory(prefix='clipcart-skills-') as tmp:
        sources = {}
        for skill in lock['skills']:
            dest = target/skill['name']
            if dest.exists():
                if not verify(dest,skill['files']): raise SystemExit(f'Modified or incomplete skill; preserved: {skill["name"]}')
            elif args.verify:
                raise SystemExit(f'Missing skill: {skill["name"]}')
            else:
                key = skill['repository'],skill['commit']
                if key not in sources:
                    source = Path(tmp)/str(len(sources))
                    run_git('init',str(source))
                    run_git('-C',str(source),'remote','add','origin','https://github.com/'+skill['repository']+'.git')
                    run_git('-C',str(source),'fetch','--depth','1','origin',skill['commit'])
                    run_git('-C',str(source),'checkout','--detach','FETCH_HEAD')
                    sources[key] = source
                original = sources[key]/skill['path']
                if not verify(original,skill['files']): raise SystemExit('Source hash mismatch: '+skill['name'])
                target.mkdir(parents=True,exist_ok=True)
                shutil.copytree(original,dest,symlinks=True)
            print('Verified:',skill['name'])
    print('All skills verified.')

if __name__ == '__main__': main()
