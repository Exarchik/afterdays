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

def center(pos,u,ox=0,oy=0):
    return ox+math.sqrt(3)*u*(pos[0]+pos[1]/2),oy+1.5*u*.75*pos[1]

def cell(px,py,u,ox=0,oy=0):
    r=(py-oy)/(1.5*u*.75);q=(px-ox)/(math.sqrt(3)*u)-r/2
    return rounded(q,r)

def polygon(px,py,u):
    return [v for i in range(6) for v in (px+u*math.cos(math.radians(30+60*i)),py+.75*u*math.sin(math.radians(30+60*i)))]
