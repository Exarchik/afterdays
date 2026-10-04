"""Immutable, bounded custom sprite pages; originals always remain editable."""
import copy
import hashlib
import json
import math
from pathlib import Path
from art_library import SIZES, WIDTHS, Library, encode, pillow

COLUMNS=8
PAGE_SIZE=64


def pack(store):
    """Prepare current and rollback catalogs together, without touching disk."""
    current=copy.deepcopy(store.data['sprites'])
    previous=copy.deepcopy(store.baseline['sprites'])
    entries=[entry for catalog in (current,previous) for entry in catalog.values()
             if entry.get('sheet','').startswith('custom/') and entry.get('inventory_sheet')]
    if not entries:return current,previous,dict(store.pending_assets)
    if all(e['sheet'].startswith('custom/atlases/') for e in entries) and not any(is_render(Path(p)) for p in store.pending_assets):
        return current,previous,dict(store.pending_assets)
    Image,_=pillow();library=Library(store);bundles={};locations={};images={}
    def crop(entry,field,size,height,columns):
        relative=f"assets/{entry[field]}_{size}.png"
        if relative not in images:images[relative]=library.image_file(relative)
        sheet=images[relative];index=entry['index'];x=index%columns*size;y=index//columns*height
        if x<0 or y<0 or x+size>sheet.width or y+height>sheet.height:raise ValueError('Некоректна клітинка атласу: '+relative)
        return sheet.crop((x,y,x+size,y+height))
    for entry in entries:
        location=(entry['sheet'],entry['inventory_sheet'],entry['index'],entry.get('columns',16),entry.get('inventory_columns',16))
        if location not in locations:
            tiles={f'sprite_{s}.png':crop(entry,'sheet',s,s,entry.get('columns',16)) for s in SIZES}
            tiles.update({f'inventory_{w}.png':crop(entry,'inventory_sheet',w,72,entry.get('inventory_columns',16)) for w in WIDTHS})
            digest=hashlib.sha256()
            for name,tile in sorted(tiles.items()):digest.update(name.encode());digest.update(tile.tobytes())
            token=digest.hexdigest();locations[location]=token;bundles.setdefault(token,tiles)
        entry['_atlas_token']=locations[location]
    pending={key:blob for key,blob in store.pending_assets.items() if not is_render(Path(key))}
    addresses={};tokens=sorted(bundles)
    for offset in range(0,len(tokens),PAGE_SIZE):
        page=tokens[offset:offset+PAGE_SIZE];columns=min(COLUMNS,len(page));rows=math.ceil(len(page)/columns)
        token=hashlib.sha256(('atlas-v1:'+','.join(page)).encode()).hexdigest()
        prefix=f'custom/atlases/{token}'
        for name in bundles[page[0]]:
            sample=bundles[page[0]][name];w,h=sample.size
            atlas=Image.new('RGBA',(columns*w,rows*h))
            for index,key in enumerate(page):atlas.paste(bundles[key][name],(index%columns*w,index//columns*h))
            relative=f'assets/{prefix}/{name}';blob=encode(atlas)
            path=store.root/relative
            if not path.exists():pending[relative]=blob
            elif path.read_bytes()!=blob:raise ValueError('Пошкоджений незмінний атлас: '+str(path))
        for index,key in enumerate(page):addresses[key]=(prefix,index,columns)
    for entry in entries:
        prefix,index,columns=addresses[entry.pop('_atlas_token')]
        entry.update(sheet=prefix+'/sprite',inventory_sheet=prefix+'/inventory',index=index,columns=columns,inventory_columns=columns)
    return current,previous,pending


def is_render(path):
    return path.name in {f'sprite_{s}.png' for s in SIZES}|{f'inventory_{w}.png' for w in WIDTHS}


def cleanup(root):
    """Remove only generated custom sheets unused by any project JSON or backup."""
    root=Path(root).resolve();custom=(root/'assets/custom').resolve();keep=set()
    def references(value):
        if isinstance(value,dict):
            for field,sizes in (('sheet',SIZES),('inventory_sheet',WIDTHS)):
                if isinstance(value.get(field),str):
                    keep.update((root/'assets'/f'{value[field]}_{size}.png').resolve() for size in sizes)
            for child in value.values():references(child)
        elif isinstance(value,list):
            for child in value:references(child)
    # An unreadable backup is a reason to retain files, never to guess that they are unused.
    for path in root.rglob('*.json*'):
        if '.git' in path.parts or not path.is_file() or not (path.name.endswith('.json') or path.name.endswith('.json.bak')):continue
        references(json.loads(path.read_text(encoding='utf-8')))
    removed=0
    for path in custom.rglob('*.png'):
        if not is_render(path) or path.resolve() in keep:continue
        if path.is_symlink() or not path.resolve().is_relative_to(custom):raise ValueError('Небезпечний шлях асета: '+str(path))
        path.unlink();removed+=1
    for path in sorted(custom.rglob('*'),key=lambda p:len(p.parts),reverse=True):
        if path.is_dir() and not path.is_symlink() and path.resolve().is_relative_to(custom):
            try:path.rmdir()
            except OSError:pass
    return removed
