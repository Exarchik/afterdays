"""Full-square top-down world textures; logical terrain is never modified."""
from pathlib import Path
from collections import OrderedDict
import json,tkinter as tk
ROOT=Path(__file__).resolve().parent/'assets'
INDEX=json.loads((ROOT/'terrain_manifest.json').read_text())
DIRS=((0,-1,1,'N'),(1,0,2,'E'),(0,1,4,'S'),(-1,0,8,'W'))
def tile_key(game,x,y):
    kind=game.world[y][x]
    def neighbor(dx,dy):return game.world[y+dy][x+dx] if 0<=x+dx<48 and 0<=y+dy<32 else None
    if kind=='road':return 'road'+str(sum(bit for dx,dy,bit,_ in DIRS if neighbor(dx,dy) in ('road','city','site')))
    if kind=='water':
        shore=next((side for dx,dy,bit,side in DIRS if neighbor(dx,dy) not in (None,'water')),None)
        return 'shore'+shore if shore else 'water'
    if kind not in ('city','site','cliff') and f'{x},{y}' in game.radiation:return 'rad1' if game.radiation[f'{x},{y}']>=3 else 'rad0'
    if kind in ('waste','forest'):return kind+str((x*17+y*31)%2)
    return kind if kind in INDEX else 'waste0'
def photo(canvas,key,width,height):
    root=canvas._root();width=max(1,int(width));height=max(1,int(height))
    if not hasattr(root,'_terrain_cache'):
        root._terrain_cache=OrderedDict();root._terrain_sheets={}
    cache=root._terrain_cache;identity=(key,width,height)
    if identity not in cache:
        cell=max(width,height)
        prepared=8<=cell<=64
        source_size=cell if prepared else 64
        if source_size not in root._terrain_sheets:
            root._terrain_sheets[source_size]=tk.PhotoImage(master=root,file=str(ROOT/(f'terrain_{source_size}.png' if source_size!=64 else 'terrain_tiles.png')))
        sheet=root._terrain_sheets[source_size]
        image=tk.PhotoImage(master=root,width=width,height=height);n=INDEX[key];x=n%8*source_size;y=n//8*source_size
        if prepared:
            image.tk.call(str(image),'copy',str(sheet),'-from',x,y,x+width,y+height,'-to',0,0)
        else:
            # Unusual very large window: scale once, then reuse cached image.
            from math import gcd
            d=gcd(width,64);e=gcd(height,64)
            enlarged=tk.PhotoImage(master=root)
            enlarged.tk.call(str(enlarged),'copy',str(sheet),'-from',x,y,x+64,y+64,'-zoom',width//d,height//e)
            image.tk.call(str(image),'copy',str(enlarged),'-subsample',64//d,64//e)
        cache[identity]=image
    cache.move_to_end(identity)
    while len(cache)>512:cache.popitem(last=False)
    return cache[identity]
def draw(canvas,game,gx,gy,x,y,size):
    if not hasattr(canvas,'tk'):return False
    left,top=round(x),round(y);width=round(x+size)-left;height=round(y+size)-top
    if width<=0 or height<=0:return False
    try:image=photo(canvas,tile_key(game,gx,gy),width,height)
    except (OSError,tk.TclError):return False
    # Keep current canvas images alive even if a resize evicts old cache entries.
    if not hasattr(canvas,'_terrain_refs'):canvas._terrain_refs=[]
    canvas._terrain_refs.append(image)
    canvas.create_image(left,top,image=image,anchor='nw');return True
