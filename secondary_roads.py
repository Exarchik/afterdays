"""Seeded winding secondary roads interrupted by dirt paths."""
import heapq
import random
import world_hex


def build(game):
    rng=random.Random('secondary-roads:'+repr(game.rng.getstate()))
    world=game.world;w=len(world[0]);h=len(world)
    cities=[tuple(p) for p in game.cities if world[p[1]][p[0]]=='city']
    sites={tuple(s['pos']) for s in game.special_sites}
    noise={(x,y):rng.uniform(0,1.2) for y in range(h) for x in range(w)}
    def path(start,end,allowed):
        queue=[(0,0,start)];cost={start:0};parent={}
        while queue:
            _,value,pos=heapq.heappop(queue)
            if value!=cost[pos]:continue
            if pos==end:
                result=[pos]
                while pos!=start:pos=parent[pos];result.append(pos)
                return result[::-1]
            for nxt in world_hex.neighbors(*pos,w,h):
                x,y=nxt
                if world[y][x] in ('water','cliff','site') or nxt in sites:continue
                if world_hex.distance(nxt,(1,1))<=3:continue
                if nxt in cities and nxt not in allowed:continue
                new=value+1+noise[nxt]+(1 if world[y][x]=='road' else 0)
                if new<cost.get(nxt,float('inf')):
                    cost[nxt]=new;parent[nxt]=pos
                    heapq.heappush(queue,(new+world_hex.distance(nxt,end),new,nxt))
        return []
    pairs=[(a,b) for i,a in enumerate(cities) for b in cities[i+1:] if 10<=world_hex.distance(a,b)<=36]
    rng.shuffle(pairs);routes=[];trails=set(map(tuple,game.trails))
    for a,b in pairs:
        if len(routes)>=5:break
        mx,my=(a[0]+b[0])//2,(a[1]+b[1])//2
        options=[(x,y) for y in range(max(1,my-7),min(h-1,my+8)) for x in range(max(1,mx-7),min(w-1,mx+8))
                 if 4<=world_hex.distance((x,y),(mx,my))<=7 and world[y][x] in ('waste','forest','ruin') and (x,y) not in sites]
        rng.shuffle(options)
        for waypoint in options[:12]:
            left=path(a,waypoint,{a,b});right=path(waypoint,b,{a,b})
            if not left or not right:continue
            route=[]
            for pos in left+right[1:]:
                if pos in route:route=route[:route.index(pos)+1]
                else:route.append(pos)
            fresh=[p for p in route if world[p[1]][p[0]] in ('waste','forest','ruin')]
            if len(fresh)<8:continue
            # Alternate intact stretches and 2–4-cell worn gaps; keep original roads.
            road=True;remaining=rng.randint(3,6);gaps=[]
            for x,y in route[1:-1]:
                if world[y][x] in ('waste','forest','ruin'):
                    if road:world[y][x]='road'
                    else:gaps.append((x,y))
                    remaining-=1
                    if remaining==0:
                        road=not road;remaining=rng.randint(3,6) if road else rng.randint(2,4)
            for p in gaps:
                i=route.index(p)
                trails.update(route[max(1,i-1):min(len(route)-1,i+2)])
            routes.append([list(p) for p in route]);break
    game.trails=[list(p) for p in sorted(trails)]
    game.init_reputation();game.reputation_state['secondary_roads_v1']=routes
