"""Migrate custom artwork with the game/editor closed; --apply creates a ZIP backup."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from entity_catalog import Store,ROOT
from art_library import Library,SIZES,WIDTHS


def pixels(library,entry,field,size,height,columns):
    image=library.image_file(f"assets/{entry[field]}_{size}.png")
    index=entry['index'];x=index%columns*size;y=index//columns*height
    return image.crop((x,y,x+size,y+height)).tobytes()


def migrate(root):
    store=Store(root);library=Library(store)
    entries={k:dict(e) for k,e in store.data['sprites'].items() if e.get('sheet','').startswith('custom/') and e.get('inventory_sheet')}
    checks={}
    for key,entry in entries.items():
        for field,sizes,height in [('sheet',SIZES,None),('inventory_sheet',WIDTHS,72)]:
            for size in sizes:
                columns=entry.get('columns' if field=='sheet' else 'inventory_columns',16)
                checks[key,field,size]=hashlib.sha256(pixels(library,entry,field,size,height or size,columns)).digest()
    sources={p:p.read_bytes() for p in (root/'assets/custom/sources').glob('*.png')}
    before=len(list((root/'assets/custom').rglob('*.png')))
    store.save();loaded=Library(Store(root))
    for (key,field,size),digest in checks.items():
        entry=loaded.entries[key];columns=entry.get('columns' if field=='sheet' else 'inventory_columns',16)
        assert hashlib.sha256(pixels(loaded,entry,field,size,72 if field=='inventory_sheet' else size,columns)).digest()==digest,(key,field,size)
    assert all(p.read_bytes()==blob for p,blob in sources.items()),'Original artwork changed'
    return dict(arts_verified=len(entries),tiles_verified=len(checks),png_before=before,png_after=len(list((root/'assets/custom').rglob('*.png'))),cleanup_warning=store.asset_cleanup_warning)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    if args.apply:
        from datetime import datetime
        backup=ROOT/'backups'/('custom-art-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.zip');backup.parent.mkdir(exist_ok=True)
        with zipfile.ZipFile(backup,'x',compression=zipfile.ZIP_DEFLATED) as archive:
            for directory in ('assets/custom','data'):
                for path in (ROOT/directory).rglob('*'):
                    if path.is_file():archive.write(path,path.relative_to(ROOT))
        with zipfile.ZipFile(backup) as archive:
            assert archive.testzip() is None,'Invalid backup'
        print('Backup:',backup,flush=True)
        print(json.dumps(migrate(ROOT),ensure_ascii=False))
    else:
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for directory in ('assets/custom','data','locales'):
                shutil.copytree(ROOT/directory,root/directory)
            shutil.copy2(ROOT/'assets/manifest.json',root/'assets/manifest.json')
            print(json.dumps(migrate(root),ensure_ascii=False))


if __name__=='__main__':main()
