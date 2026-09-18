"""Pack the generated 4x3 trophy sheet into runtime-size transparent atlases."""
from pathlib import Path
import json
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
source=Image.open(ROOT/'assets/trophies_source.png').convert('RGBA')
models=json.loads((ROOT/'data/monsters.json').read_text())
keys=sorted(models,key=lambda key:models[key]['legacy_index'])
icons=[]
for n,key in enumerate(keys):
    x,y=n%4,n//4
    rows=(0,362,704,1086)  # Hand-checked empty gutters in the generated source.
    box=(round(x*source.width/4),rows[y],round((x+1)*source.width/4),rows[y+1])
    tile=source.crop(box);bbox=tile.getchannel('A').getbbox()
    assert bbox,key
    icons.append(tile.crop(bbox))
for size in (16,24,32,48,64,96,144,192):
    atlas=Image.new('RGBA',(4*size,3*size))
    for n,icon in enumerate(icons):
        icon=icon.copy();icon.thumbnail((round(size*.88),round(size*.88)),Image.Resampling.LANCZOS)
        atlas.alpha_composite(icon,(n%4*size+(size-icon.width)//2,n//4*size+(size-icon.height)//2))
    atlas.save(ROOT/f'assets/trophies_{size}.png')
p=ROOT/'data/sprites.json';data=json.loads(p.read_text())
for n,key in enumerate(keys):data['trophy_'+key]=dict(index=n,sheet='trophies',columns=4)
p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
