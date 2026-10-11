"""Repack current and rollback art together; verify pixels before removing stale pages."""
import hashlib
import io
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import custom_atlases as atlas


def rebuild(root):
    root=Path(root).resolve()
    paths=[root/'data/sprites.json',root/'data/sprites.json.bak']
    original=[p.read_bytes() for p in paths]
    catalogs=[json.loads(blob) for blob in original]
    store=SimpleNamespace(root=root,data={'sprites':catalogs[0]},baseline={'sprites':catalogs[1]},pending_assets={})
    current,previous,pending=atlas.pack(store,force=True)
    def signatures(catalog,assets):
        sheets={};tiles={};result={}
        for key,e in catalog.items():
            if not e.get('sheet','').startswith('custom/'):continue
            location=tuple(e.get(k) for k in ('sheet','inventory_sheet','index','columns','inventory_columns'))
            if location not in tiles:
                digest=hashlib.sha256()
                for field,sizes in [('sheet',atlas.SIZES),('inventory_sheet',atlas.WIDTHS)]:
                    for size in sizes:
                        relative=f'assets/{e[field]}_{size}.png'
                        if relative not in sheets:
                            blob=assets.get(relative)
                            with Image.open(io.BytesIO(blob) if blob is not None else root/relative) as image:sheets[relative]=image.convert('RGBA')
                        height=size if field=='sheet' else 72
                        cols=e.get('columns' if field=='sheet' else 'inventory_columns',16)
                        x=e['index']%cols*size;y=e['index']//cols*height
                        digest.update(sheets[relative].crop((x,y,x+size,y+height)).tobytes())
                tiles[location]=digest.hexdigest()
            result[key]=tiles[location]
        return result
    for old,new in zip(catalogs,(current,previous)):
        assert old.keys()==new.keys()
        assert signatures(old,{})==signatures(new,pending),'Repack changed icon pixels'
    sources={p:hashlib.sha256(p.read_bytes()).digest() for p in (root/'assets/custom/sources').glob('*.png')}
    # Detect an editor saving concurrently before replacing either catalog.
    assert all(p.read_bytes()==blob for p,blob in zip(paths,original)),'Catalog changed during rebuild'
    for relative,blob in pending.items():
        path=(root/relative).resolve()
        assert path.is_relative_to((root/'assets/custom/atlases').resolve())
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(blob)
    try:
        for path,data in zip(paths,(current,previous)):
            temp=path.with_name(path.name+'.rebuild.tmp')
            temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            os.replace(temp,path)
    except OSError:
        for path,blob in zip(paths,original):path.write_bytes(blob)
        raise
    before=list((root/'assets/custom/atlases').glob('*/*.png'))
    size_before=sum(p.stat().st_size for p in before)
    removed=atlas.cleanup(root)
    after=list((root/'assets/custom/atlases').glob('*/*.png'))
    assert all(p.exists() and hashlib.sha256(p.read_bytes()).digest()==digest for p,digest in sources.items())
    print(json.dumps(dict(verified_current=len(signatures(current,{})),verified_backup=len(signatures(previous,{})),
        removed_files=removed,remaining_pages=len({p.parent for p in after}),
        freed_bytes=size_before-sum(p.stat().st_size for p in after),sources_preserved=len(sources)),indent=2))


if __name__=='__main__':rebuild(Path(__file__).resolve().parents[1])
