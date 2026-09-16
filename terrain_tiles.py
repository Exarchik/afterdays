"""Full-square top-down world textures; logical terrain is never modified."""
from pathlib import Path
from collections import OrderedDict
import json,tkinter as tk
ROOT=Path(__file__).resolve().parent/'assets'
INDEX=json.loads((ROOT/'terrain_v2.json').read_text())
DIRS=((0,-1,1,'N'),(1,0,2,'E'),(0,1,4,'S'),(-1,0,8,'W'))
def tile_key(game,x,y):
    kind=game.world[y][x]
    def neighbor(dx,dy):
        xx,yy=x+dx,y+dy
        return game.world[yy][xx] if 0<=yy<len(game.world) and 0<=xx<len(game.world[yy]) else kind
    if kind=='road':
        bits=sum(bit for dx,dy,bit,_ in DIRS if neighbor(dx,dy) in ('road','city','site'))
        surrounding=[neighbor(dx,dy) for dx,dy,_,_ in DIRS if neighbor(dx,dy) in ('forest','ruin','cliff','water')]
        family=max(('forest','ruin','cliff','water'),key=lambda k:surrounding.count(k)) if surrounding else 'waste'
        if f'{x},{y}' in game.radiation:family='rad'
        key='road'+str(bits) if family=='waste' else f'road_{family}_{bits}'
    elif kind in ('water','forest','cliff','ruin'):
        directions=[(dx,dy,bit) for dx,dy,bit,_ in DIRS]+[(-1,-1,16),(1,-1,32),(1,1,64),(-1,1,128)]
        bits=sum(bit for dx,dy,bit in directions if neighbor(dx,dy)==kind)
        key=f'{kind}_{bits}'
    elif kind in ('city','site'):key=kind
    else:key='waste'+str((x*17+y*31)%8)
    if kind not in ('city','site','road') and f'{x},{y}' in game.radiation:key+='_rad'
    return key
def photo(canvas,key,width,height):
    root=canvas._root();width=max(1,int(width));height=max(1,int(height))
    if not hasattr(root,'_terrain_cache'):
        root._terrain_cache=OrderedDict();root._terrain_sheets={}
    cache=root._terrain_cache;identity=(key,width,height)
    if identity not in cache:
        if 64 not in root._terrain_sheets:
            root._terrain_sheets[64]=tk.PhotoImage(master=root,file=str(ROOT/'terrain_v2.png'))
        sheet=root._terrain_sheets[64]
        image=tk.PhotoImage(master=root,width=width,height=height)
        n=INDEX[key];x=n%32*64;y=n//32*64
        # Standard-library Tk scaling, cached by tile and display dimensions.
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
