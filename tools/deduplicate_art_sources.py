"""Share byte-identical originals, preserving current catalogs and JSON backups.

Run with the editor closed. Defaults to a dry run; --apply performs the migration.
Originals are collected in assets/custom/sources; rendered sprites stay in place.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile


def compact(root, apply=False):
    root=Path(root).resolve();assets=root/'assets';custom=(assets/'custom').resolve()
    groups={}
    for path in sorted(set(custom.glob('*/source.png')) | set(custom.glob('sources/*.png'))):
        if path.is_symlink() or not path.resolve().is_relative_to(custom):
            raise ValueError('Unsafe source path: '+str(path))
        blob=path.read_bytes();digest=hashlib.sha256(blob).hexdigest()
        groups.setdefault(digest,[]).append((path,blob))
    duplicates={};saved=0;duplicate_count=0;created={}
    for digest,group in groups.items():
        canonical=custom/'sources'/f'{digest}.png';blob=group[0][1]
        if canonical.is_symlink() or not canonical.resolve().is_relative_to(custom):
            raise ValueError('Unsafe source path: '+str(canonical))
        if canonical.exists() and canonical.read_bytes()!=blob:raise ValueError('Source hash collision')
        if not canonical.exists():created[canonical]=blob
        duplicate_count+=len(group)-1;saved+=(len(group)-1)*len(blob)
        for path,other in group:
            if other!=blob:raise ValueError('Source hash collision')
            if path!=canonical:duplicates[path]=canonical
    replacements={old.relative_to(assets).as_posix():new.relative_to(assets).as_posix() for old,new in duplicates.items()}
    changes={}
    # Include .json.bak: restoring the previous catalog must still work.
    for path in root.rglob('*'):
        if '.git' in path.parts or not path.is_file() or not (path.name.endswith('.json') or path.name.endswith('.json.bak')):continue
        before=path.read_bytes();text=before.decode('utf-8')
        after=text
        for old,new in replacements.items():
            for prefix in ('','assets/'):
                after=after.replace(json.dumps(prefix+old),json.dumps(prefix+new))
        if after!=text:
            json.loads(after)
            changes[path]=(before,after.encode('utf-8'))
    report=dict(duplicate_sources=duplicate_count,sources_relocated=len(duplicates),bytes_saved=saved,catalogs_changed=len(changes),applied=apply)
    if not apply:return report
    staged={};replaced=[]
    try:
        for path,blob in created.items():
            path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('xb') as stream:stream.write(blob)
        for path,(before,after) in changes.items():
            fd,name=tempfile.mkstemp(dir=path.parent,suffix='.tmp');staged[path]=Path(name)
            with os.fdopen(fd,'wb') as stream:stream.write(after)
        for path,(before,_) in changes.items():
            if path.read_bytes()!=before:raise ValueError('Catalog changed during migration: '+str(path))
        for path in changes:
            os.replace(staged[path],path);replaced.append(path)
    except Exception:
        for path in reversed(replaced):path.write_bytes(changes[path][0])
        raise
    finally:
        for path in staged.values():path.unlink(missing_ok=True)
    # References are durable before any deletion. An interrupted cleanup is safe to rerun.
    for old,new in duplicates.items():
        if not old.resolve().is_relative_to(custom) or not new.resolve().is_relative_to(custom):raise ValueError('Unsafe cleanup path')
        if old.read_bytes()!=new.read_bytes():raise ValueError('Source changed during migration')
        old.unlink()
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    print(json.dumps(compact(Path(__file__).resolve().parents[1],args.apply),indent=2))
