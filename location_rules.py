"""Terrain illustration pools and hex-adjacency classification."""
from functools import lru_cache
import content
import world_hex

BASES={'waste':'Пустка','forest':'Ліс','ruin':'Руїни','road':'Дорога'}
TYPES={base+suffix:name+label for base,name in BASES.items()
       for suffix,label in (('',''),('_lake',' біля озера'),('_mountain',' біля гір'))}

def defaults():return {key:[] for key in TYPES}

@lru_cache(maxsize=1)
def catalog():
    try:return content.read('locations.json')
    except FileNotFoundError:return defaults()

def terrain_type(game,x,y):
    base=game.world[y][x]
    if base not in BASES:return None
    near={game.world[ny][nx] for nx,ny in world_hex.neighbors(x,y,len(game.world[0]),len(game.world))}
    suffix='_lake' if 'water' in near else '_mountain' if 'cliff' in near else ''
    return base+suffix

def validate(data,art):
    if not isinstance(data,dict):return ['Локації: потрібен каталог типів місцевості.']
    errors=[]
    for key,values in data.items():
        if key not in TYPES:errors.append('Локації: невідомий тип '+str(key));continue
        if not isinstance(values,list) or any(not isinstance(value,str) for value in values):
            errors.append(TYPES[key]+': потрібен список ID артів.');continue
        if len(values)!=len(set(values)):errors.append(TYPES[key]+': арт повторюється.')
        for value in values:
            if value not in art:errors.append(TYPES[key]+': невідомий арт '+value)
    return errors
