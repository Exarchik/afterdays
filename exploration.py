"""Search rewards, quest counts and varied dungeon layouts."""
import math

def objective_count(rng,kind):
    if kind is None:return rng.randint(3,5)
    # Tough or unusual enemies require fewer kills/trophies.
    return rng.randint(2,3) if kind in (4,7,9,10,11) else rng.randint(3,4) if kind in (5,6,8) else rng.randint(4,5)

def dungeon_layout(rng):
    w,h=31,27
    chosen=[0]+rng.sample(list(range(1,9)),rng.randint(3,7))
    rooms=[];floor=set()
    for cell in chosen:
        x=1+(cell%3)*10+rng.randint(0,2);y=1+(cell//3)*9+rng.randint(0,1)
        rw,rh=rng.randint(4,7),rng.randint(4,6)
        rooms.append([x,y,rw,rh]);floor.update((xx,yy) for xx in range(x,x+rw) for yy in range(y,y+rh))
    centers=[(x+rw//2,y+rh//2) for x,y,rw,rh in rooms]
    edges=[(n,min(range(n),key=lambda j:math.dist(centers[n],centers[j]))) for n in range(1,len(rooms))]
    edges+=rng.sample([(i,j) for i in range(len(rooms)) for j in range(i) if (i,j) not in edges],rng.randint(0,2))
    for i,j in edges:
        x,y=centers[i];tx,ty=centers[j];horizontal=rng.choice([True,False])
        while (x,y)!=(tx,ty):
            floor.add((x,y))
            if (horizontal and x!=tx) or y==ty:x+=1 if tx>x else -1
            else:y+=1 if ty>y else -1
        floor.add((tx,ty))
    return w,h,rooms,floor,list(centers[0]),list(max(centers[1:],key=lambda p:math.dist(p,centers[0])))
