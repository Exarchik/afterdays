"""Pointy-top odd-row offset world grid. Combat keeps its axial hexgrid module.

Stored [x,y] coordinates are unchanged: odd rows are shifted half a cell right.
All six edges cost one world turn, including edges whose array delta is (1,1).
"""
import math


def adjacent(pos):
    x,y=pos
    shift=int(y)&1
    return ((x+1,y),(x+shift,y+1),(x+shift-1,y+1),
            (x-1,y),(x+shift-1,y-1),(x+shift,y-1))


def neighbors(x,y,w,h):
    return [p for p in adjacent((x,y)) if 0<=p[0]<w and 0<=p[1]<h]


def axial(pos):
    x,y=pos
    return x-(y-(y&1))//2,y


def distance(a,b):
    aq,ar=axial(a);bq,br=axial(b)
    return max(abs(aq-bq),abs(ar-br),abs(aq+ar-bq-br))


def center(pos,radius=1,ox=0,oy=0):
    x,y=pos
    # Linear parity interpolation keeps animated travel straight between centers.
    shift=.5*(1-abs(y%2-1))
    return ox+math.sqrt(3)*radius*(x+shift),oy+1.5*radius*y


def cell(px,py,radius=1,ox=0,oy=0):
    if radius<=0:raise ValueError('Hex radius must be positive')
    x,y=(px-ox)/radius,(py-oy)/radius
    q,r=x/math.sqrt(3)-y/3,2*y/3
    s=-q-r;a,b,c=round(q),round(r),round(s)
    errors=(abs(a-q),abs(b-r),abs(c-s))
    if errors[0]>errors[1] and errors[0]>errors[2]:a=-b-c
    elif errors[1]>errors[2]:b=-a-c
    return a+(b-(b&1))//2,b


def polygon(cx,cy,radius):
    return [v for n in range(6) for v in (cx+radius*math.cos(math.radians(-90+n*60)),
                                         cy+radius*math.sin(math.radians(-90+n*60)))]


def edge(a,b,radius=1,ox=0,oy=0):
    direction=adjacent(a).index(tuple(b))
    vertices=polygon(*center(a,radius,ox,oy),radius)
    points=list(zip(vertices[::2],vertices[1::2]))
    return (*points[(direction+1)%6],*points[(direction+2)%6])


def key_delta(key,y):
    """Q/W, A/D, Z/X follow the six screen directions; E stays interaction."""
    direction={'d':0,'right':0,'x':1,'down':1,'z':2,'a':3,'left':3,
               'q':4,'w':5,'up':5,'s':2}.get(key)
    if direction is None:return None
    target=adjacent((0,y))[direction]
    return target[0],target[1]-y
