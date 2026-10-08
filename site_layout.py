import world_hex
"""Well-spaced special sites and shortest trails to the existing road network."""
import math
from collections import deque

def place(game,count):
    reachable=game.reachable_world((5,5))
    pool=[p for p in sorted(reachable) if 1<=p[0]<len(game.world[0])-1 and 1<=p[1]<len(game.world)-1 and game.world[p[1]][p[0]] not in ('road','city','site') and all(world_hex.distance(p,c)>2 for c in game.cities)]
    starts=[p for p in pool if 3<=world_hex.distance(p,(5,5))<=6]
    best=[]
    for attempt in range(24):
        selected=[game.rng.choice(starts or pool)]
        distances={p:world_hex.distance(p,selected[0]) for p in pool}
        while len(selected)<count:
            candidates=[p for p in pool if distances[p]>=7]
            if not candidates:break
            # Farthest sampling avoids the dead ends of uniform random placement.
            pos=max(candidates,key=lambda p:distances[p]+game.rng.random()*.8)
            selected.append(pos)
            for p in candidates:distances[p]=min(distances[p],world_hex.distance(p,pos))
        if len(selected)>len(best):best=selected
        if len(best)>=count:return best[:count]
    # Guaranteed grid fallback. Reserve space before clearing small terrain obstacles.
    layouts=[]
    for ox in range(7):
        for oy in range(7):
            pts=[(x,y) for y in range(oy,32,7) for x in range(ox,len(game.world[0]),7) if 1<=x<len(game.world[0])-1 and 1<=y<len(game.world)-1 and all(world_hex.distance((x,y),c)>1.5 for c in game.cities)]
            if len(pts)>=count:layouts.append(pts)
    pts=max(layouts,key=lambda ps:sum(p in reachable for p in ps))
    start=min(pts,key=lambda p:abs(world_hex.distance(p,(5,5))-4))
    pts.remove(start);game.rng.shuffle(pts);selected=[start]+pts[:count-1]
    for pos in selected:
        if pos not in reachable:
            target=min(reachable,key=lambda p:world_hex.distance(pos,p));x,y=pos
            while (x,y)!=target:
                if game.world[y][x] in ('water','cliff'):game.world[y][x]='waste'
                x,y=world_hex.line_path((x,y),target)[1]
            reachable=game.reachable_world((5,5))
    return selected

def road_path(game,start):
    from world_hex import neighbors
    start=tuple(start);queue=deque([start]);previous={start:None}
    while queue:
        pos=queue.popleft()
        if game.world[pos[1]][pos[0]]=='road':
            route=[]
            while pos is not None:route.append(pos);pos=previous[pos]
            return route[::-1]
        for nxt in neighbors(*pos,len(game.world[0]),len(game.world)):
            if nxt not in previous and game.passable(*nxt):previous[nxt]=pos;queue.append(nxt)
    return []
