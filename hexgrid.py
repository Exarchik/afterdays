"""Axial hex coordinates for combat; world tiles keep their square topology."""
import math
from collections import deque
DIRECTIONS=((1,0),(-1,0),(0,1),(0,-1),(1,-1),(-1,1))

def neighbors(x,y,w,h):
    return [(x+dx,y+dy) for dx,dy in DIRECTIONS if 0<=x+dx<w and 0<=y+dy<h]

def distance(a,b):
    dx,dy=a[0]-b[0],a[1]-b[1]
    return max(abs(dx),abs(dy),abs(dx+dy))

def path_to(start,goal,w,h,blocked):
    start,goal=tuple(start),tuple(goal);blocked=set(map(tuple,blocked))
    if not (0<=goal[0]<w and 0<=goal[1]<h) or goal in blocked:return None
    previous={start:None};queue=deque([start])
    while queue:
        pos=queue.popleft()
        if pos==goal:
            route=[]
            while pos!=start:route.append(pos);pos=previous[pos]
            return route[::-1]
        for nxt in neighbors(*pos,w,h):
            if nxt not in previous and nxt not in blocked:previous[nxt]=pos;queue.append(nxt)
    return None

def rounded(q,r):
    s=-q-r;a,b,c=round(q),round(r),round(s)
    errors=(abs(a-q),abs(b-r),abs(c-s))
    if errors[0]>errors[1] and errors[0]>errors[2]:a=-b-c
    elif errors[1]>errors[2]:b=-a-c
    return a,b

def visible(a,b,walls):
    n=int(distance(a,b));blocked=set(map(tuple,walls))
    # A tiny consistent nudge resolves exact hex-edge ties symmetrically.
    return all(rounded(a[0]+(b[0]-a[0])*i/n+1e-7,a[1]+(b[1]-a[1])*i/n+1e-7) not in blocked for i in range(1,n))

# Diamond footprint with clockwise-sloping q axis. The common affine
# projection also transforms tile vertices, so adjacent edges meet exactly.
HEIGHT_SCALE=1.2
VERTICAL=1.125*HEIGHT_SCALE

def center(pos,u,ox=0,oy=0):
    return ox+math.sqrt(3)*u*(pos[0]-pos[1]),oy+VERTICAL*u*(pos[0]+pos[1])

def cell(px,py,u,ox=0,oy=0):
    diff=(px-ox)/(math.sqrt(3)*u);total=(py-oy)/(VERTICAL*u)
    return rounded((total+diff)/2,(total-diff)/2)

def polygon(px,py,u):
    points=[]
    for i in range(6):
        angle=math.radians(30+60*i);x,y=math.cos(angle),math.sin(angle)
        q=x/math.sqrt(3)-y/3;r=2*y/3
        points.extend(center((q,r),u,px,py))
    return points

def bounds(w,h):
    points=[]
    for pos in ((0,0),(w-1,0),(0,h-1),(w-1,h-1)):
        xy=polygon(*center(pos,1),1);points.extend(zip(xy[::2],xy[1::2]))
    return min(x for x,y in points),min(y for x,y in points),max(x for x,y in points),max(y for x,y in points)
