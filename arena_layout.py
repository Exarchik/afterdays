"""Hex-shaped outdoor arenas with world-oriented entry and shoreline."""
import math
import hexgrid
import world_hex
from organic_arenas import connected

def build(game):
    b=game.battle
    if not b or b.get('dungeon'):return
    # Half-row centering keeps the reduced outline symmetric across 20 rows.
    w,h=19,28;center=hexgrid.center((9,13.5),1);rx,ry=16,18*20/27
    def relative(p):
        x,y=hexgrid.center(p,1);return (x-center[0])/rx,(y-center[1])/ry
    floor={p for y in range(h) for x in range(w) for p in [(x,y)]
           if abs(relative(p)[0])<=1+1e-9 and abs(relative(p)[1])+.5*abs(relative(p)[0])<=1+1e-9}
    origin=(game.x,game.y);ox,oy=world_hex.center(origin)
    neighbours=world_hex.neighbors(*origin,len(game.world[0]),len(game.world))
    vectors=[]
    for p in neighbours:
        nx,ny=world_hex.center(p);length=math.hypot(nx-ox,ny-oy)
        vectors.append(((nx-ox)/length,(ny-oy)/length,game.world[p[1]][p[0]]))
    water=set();shore=set()
    for p in floor:
        x,y=relative(p)
        if not vectors:continue
        dx,dy,kind=max(vectors,key=lambda v:x*v[0]+y*v[1])
        edge=max(abs(x),abs(y)+.5*abs(x))
        if kind=='water':
            if edge>.82:water.add(p)
            elif edge>.64:shore.add(p)
    walk=floor-water
    entry=getattr(game,'_entering_world',None)
    if not entry or list(entry[1])!=list(origin):
        entry=getattr(game,'last_world_entry',None)
    direction=(-1.,0.)
    if entry and list(entry[1])==list(origin) and tuple(entry[0]) in world_hex.adjacent(origin):
        ex,ey=world_hex.center(entry[0]);length=math.hypot(ex-ox,ey-oy)
        direction=((ex-ox)/length,(ey-oy)/length)
    dx,dy=direction
    def projection(p):
        x,y=relative(p);return x*dx+y*dy
    def entry_score(p):
        x,y=relative(p);return projection(p)-.6*abs(x*dy-y*dx),p
    start=max(walk,key=entry_score)
    walk=connected(walk,start)
    # NPCs are distributed on the opposing side, not clustered on one cell.
    candidates=sorted((p for p in walk if projection(p)<-.35),key=lambda p:(projection(p),p))
    game.rng.shuffle(candidates)
    if len(candidates)<len(b['enemies']):candidates=sorted(walk-{start},key=lambda p:(projection(p),p))
    spawns=candidates[:len(b['enemies'])]
    density={'forest':.14,'ruin':.17,'city':.12}.get(b.get('biome'),.07)
    obstacles={p for p in sorted(walk) if game.rng.random()<density and p!=start and p not in spawns}
    # Reserve routes from the entry to every actor before checking connectivity.
    void={(x,y) for y in range(h) for x in range(w)}-walk
    for p in spawns:obstacles.difference_update(hexgrid.path_to(start,p,w,h,void) or [])
    for p in sorted(obstacles):
        if connected(walk-obstacles,start)==walk-obstacles:break
        obstacles.remove(p)
    b.update(w=w,h=h,pos=list(start),floor=[list(p) for p in sorted(floor)],
             walls=[list(p) for p in sorted(void|obstacles)],organic=True,
             hex_arena=True,entry_direction=list(direction),world_origin=list(origin),
             water_cells=[list(p) for p in sorted(water)],shore_cells=[list(p) for p in sorted(shore)],
             arena_center=list(center),arena_extent=[rx,ry])
    for actor,p in zip(b['enemies'],spawns):actor['pos']=list(p)
    b['entrance047']=list(start)
    # Widened road stays clear of generated props, never of water or void.
    import arena_tiles
    trial=dict(b,walls=[list(p) for p in sorted(void)])
    roads=arena_tiles.road_cells(trial,arena_tiles.road_directions(game,b))
    obstacles.difference_update(roads)
    b['walls']=[list(p) for p in sorted(void|obstacles)]
