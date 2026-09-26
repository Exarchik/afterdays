"""Seeded town placement and a connected, varying overworld road network."""
import math
import random
WIDTH=62
HEIGHT=32

def build(rng_state):
    # Independent stream: layout changes do not consume combat/event randomness.
    rng=random.Random('town-layout:'+repr(rng_state))
    cities=[[5,5]]
    sectors=[(col,row) for row in range(3) for col in range(4) if (col,row)!=(0,0)]
    rng.shuffle(sectors)
    for col,row in sectors:
        candidates=[(x,y) for y in range(max(2,row*10+2),min(30,(row+1)*10))
                    for x in range(max(2,col*WIDTH//4+2),min(WIDTH-2,(col+1)*WIDTH//4))
                    if all(math.dist((x,y),p)>=6 for p in cities)]
        # Fixed sectors have enough space; a farthest point also guarantees termination.
        if not candidates:
            candidates=[max(((x,y) for y in range(2,30) for x in range(2,WIDTH-2)),key=lambda p:min(math.dist(p,c) for c in cities))]
        cities.append(list(rng.choice(candidates)))
    available=set(range(1,12));selected=[0]
    for target in (WIDTH*.25,WIDTH*.5,WIDTH*.75,WIDTH-4):
        city=min(available,key=lambda i:(abs(cities[i][0]-target),cities[i][1]))
        selected.append(city);available.remove(city)
    assigned=dict(zip((0,2,3,7,10),selected));rest=iter(sorted(available))
    cities=[cities[assigned[i] if i in assigned else next(rest)] for i in range(12)]
    world=[[rng.choices(('waste','forest','ruin'),(65,23,12))[0] for _ in range(WIDTH)] for _ in range(HEIGHT)]
    connected={0};edges=[]
    while len(connected)<len(cities):
        distance,a,b=min((math.dist(cities[a],cities[b]),a,b) for a in sorted(connected) for b in range(len(cities)) if b not in connected)
        edges.append((a,b));connected.add(b)
    extra=[(a,b) for a in range(12) for b in range(a+1,12) if (a,b) not in edges and (b,a) not in edges]
    extra.sort(key=lambda pair:math.dist(cities[pair[0]],cities[pair[1]]))
    edges+=rng.sample(extra[:20],2)
    for a,b in edges:
        x,y=cities[a];tx,ty=cities[b]
        if rng.randrange(2):
            mid=rng.randint(min(x,tx),max(x,tx));points=[(mid,y),(mid,ty),(tx,ty)]
        else:
            mid=rng.randint(min(y,ty),max(y,ty));points=[(x,mid),(tx,mid),(tx,ty)]
        world[y][x]='road'
        for px,py in points:
            while (x,y)!=(px,py):
                if x!=px:x+=1 if px>x else -1
                else:y+=1 if py>y else -1
                world[y][x]='road'
    for x,y in cities:world[y][x]='city'
    return cities,world
