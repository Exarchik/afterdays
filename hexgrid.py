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

# Flat-top hexes, compressed vertically, with the original cell area.
# Both centers and vertices use the same axial projection.
HEIGHT_SCALE=.9
HALF_WIDTH=math.sqrt(3)
HALF_HEIGHT=.75*HEIGHT_SCALE

def center(pos,u,ox=0,oy=0):
    """Project axial coordinates to centers of flattened flat-top hexes."""
    q,r=pos
    return ox+1.5*HALF_WIDTH*u*q,oy+HALF_HEIGHT*u*(q+2*r)

def cell(px,py,u,ox=0,oy=0):
    """Invert the projection and select the hex under the mouse."""
    q=(px-ox)/(1.5*HALF_WIDTH*u)
    r=((py-oy)/(HALF_HEIGHT*u)-q)/2
    return rounded(q,r)

def polygon(px,py,u):
    """Return six vertices with horizontal top and bottom edges."""
    w,h=HALF_WIDTH*u,HALF_HEIGHT*u
    return [px+w,py,px+w/2,py+h,px-w/2,py+h,
            px-w,py,px-w/2,py-h,px+w/2,py-h]

def bounds(w,h):
    points=[]
    for pos in ((0,0),(w-1,0),(0,h-1),(w-1,h-1)):
        xy=polygon(*center(pos,1),1);points.extend(zip(xy[::2],xy[1::2]))
    return min(x for x,y in points),min(y for x,y in points),max(x for x,y in points),max(y for x,y in points)
