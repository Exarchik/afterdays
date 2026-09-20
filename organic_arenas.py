"""Connected hex floors with irregular rooms, branching corridors and exposed rims."""
from collections import deque
import hexgrid

def connected(floor,start):
    if start not in floor:return set()
    seen={start};queue=deque([start])
    while queue:
        x,y=queue.popleft()
        for dx,dy in hexgrid.DIRECTIONS:
            p=x+dx,y+dy
            if p in floor and p not in seen:seen.add(p);queue.append(p)
    return seen

def brush(floor,center,radius,w,h):
    cx,cy=center
    for x in range(cx-radius,cx+radius+1):
        for y in range(cy-radius,cy+radius+1):
            if 0<x<w-1 and 0<y<h-1 and hexgrid.distance(center,(x,y))<=radius:floor.add((x,y))

def dungeon(rng):
    w,h=31,27;floor=set();rooms=[];centers=[]
    cells=[0]+rng.sample(list(range(1,9)),rng.randint(3,7))
    for cell in cells:
        center=(4+cell%3*10+rng.randint(-1,1),4+cell//3*9+rng.randint(-1,1));radius=rng.randint(2,4)
        centers.append(center);rooms.append([*center,radius,radius]);brush(floor,center,radius-1,w,h)
        edge=set();brush(edge,center,radius,w,h)
        floor.update(p for p in sorted(edge) if p in floor or rng.random()<.72)
    edges=[(n,min(range(n),key=lambda i:hexgrid.distance(centers[n],centers[i]))) for n in range(1,len(centers))]
    alternatives=[(i,j) for i in range(len(centers)) for j in range(i) if (i,j) not in edges]
    edges+=rng.sample(alternatives,min(len(alternatives),rng.randint(0,2)))
    for i,j in edges:
        pos=centers[i];target=centers[j];radius=rng.choice([0,0,1])
        while pos!=target:
            brush(floor,pos,radius,w,h)
            choices=[p for p in hexgrid.neighbors(*pos,w,h) if hexgrid.distance(p,target)<hexgrid.distance(pos,target)]
            pos=rng.choice(choices)
        brush(floor,target,radius,w,h)
    # Small interior holes are allowed only if the entire remaining floor stays connected.
    protected=set(centers)
    for _ in range(rng.randint(1,4)):
        candidates=[p for p in sorted(floor-protected) if all((p[0]+dx,p[1]+dy) in floor for dx,dy in hexgrid.DIRECTIONS)]
        if not candidates:break
        p=rng.choice(candidates);trial=floor-{p}
        if len(connected(trial,centers[0]))==len(trial):floor=trial
    floor=connected(floor,centers[0])
    chest=max(centers[1:],key=lambda p:hexgrid.distance(p,centers[0]))
    return w,h,rooms,floor,list(centers[0]),list(chest)

def arena(game):
    b=game.battle;w,h=b['w'],b['h'];rng=game.rng
    floor=set()
    for x in range(w):
        for y in range(h):
            radius=((x-(w-1)/2)/(w*.55))**2+((y-(h-1)/2)/(h*.51))**2
            if radius<.65 or radius<1.1 and rng.random()<.8:floor.add((x,y))
    # Preserve the established entrance, escape edge and enemy placements.
    anchors=[tuple(b['pos'])]+[tuple(e['pos']) for e in b['enemies']]+[(0,5)]
    for p in anchors:
        floor.add(p)
        floor.update(hexgrid.path_to(tuple(b['pos']),p,w,h,set()) or [])
    if b.get('biome')=='road':floor.update((x,y) for x in range(w) for y in range(4,7))
    floor=connected(floor,tuple(b['pos']))
    obstacles=set(map(tuple,b['walls']))&floor-set(anchors)
    walk=floor-obstacles
    # Remove only obstacles that disconnect traversable ground.
    for p in sorted(obstacles):
        if len(connected(walk,tuple(b['pos'])))==len(walk):break
        walk.add(p);obstacles.remove(p)
    b['floor']=[list(p) for p in sorted(floor)]
    b['walls']=[list((x,y)) for y in range(h) for x in range(w) if (x,y) not in floor or (x,y) in obstacles]
    b['organic']=True

def boundary_edges(floor):
    """Unit-scale exposed edges only; internal shared hex edges disappear."""
    edges={}
    for pos in floor:
        xy=hexgrid.polygon(*hexgrid.center(pos,1),1);points=list(zip(xy[::2],xy[1::2]))
        for a,b in zip(points,points[1:]+points[:1]):
            key=tuple(sorted((tuple(round(v,7) for v in a),tuple(round(v,7) for v in b))))
            if key in edges:del edges[key]
            else:edges[key]=(a,b)
    return list(edges.values())
