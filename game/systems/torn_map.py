"""Torn map: ragged paper pieces of the real world around the quest target.

The sheet shows a fragment of the actual generated world (a 9×7 hex window around
the target, chosen so the target is off-centre and a city, road or water is visible).
It is cut into cols×rows pieces with torn edges. Pieces lie loose on a table; a click
turns a piece (with everything glued to it) by 90°, a drag moves it. When a piece lands
next to its true neighbour with the same rotation, they glue together. One group = solved.

Positions are in piece units (one piece = 1×1); the UI only scales them.
Everything is deterministic from the quest ID; there is no failure.
"""
import math
import random

import world_hex

VERSION=1
# Editor-tunable settings: (default, minimum, maximum).
SETTINGS={'cols':(4,3,5),'rows':(3,3,4),'rotate':(1,0,1)}
VIEW=(9,7)          # hexes of the world window that holds the target
TABLE=(6.4,4.4)     # table size in piece units
SNAP=.15            # gluing tolerance in piece units
LANDMARKS=('road','city','site','water')


def settings_for(spec):
    spec=spec or {}
    return {key:spec.get(key,default) for key,(default,_,_) in SETTINGS.items()}


def validate_settings(spec,prefix=''):
    return [f'{prefix}Некоректне поле {key}: ціле число від {low} до {high}'
            for key,(_,low,high) in SETTINGS.items()
            if key in spec and (type(spec[key]) is not int or not low<=spec[key]<=high)]


# ---------- the world fragment ----------
def choose_window(world,cities,target,rng):
    """A VIEW-sized window holding the target off-centre, preferring visible landmarks."""
    w,h=len(world[0]),len(world);cols,rows=VIEW;tx,ty=target
    city_cells={tuple(p) for p in cities}
    best=None
    for _ in range(60):
        vx=tx-rng.randint(2,cols-3);vy=ty-rng.randint(2,rows-3)
        vx=max(0,min(max(0,w-cols),vx));vy=max(0,min(max(0,h-rows),vy))
        cells=[(x,y) for y in range(vy+1,min(h,vy+rows)-1) for x in range(vx+1,min(w,vx+cols)-1)]
        kinds=[world[y][x] for x,y in cells]
        edge=vx>=1 and vy>=1 and vx+cols<=w-1 and vy+rows<=h-1
        score=(3*sum(c in city_cells for c in cells)+min(6,sum(k in LANDMARKS for k in kinds))
               +len(set(kinds))+2*edge+rng.random())
        if best is None or score>best[0]:best=(score,[vx,vy,cols,rows])
    return best[1]


def geometry(window,cols,rows,bounds=None):
    """Hex radius and offset (piece units) that fit the window onto a cols×rows sheet.

    The fitted window is trimmed by about half a hex so the paper is fully covered;
    the renderer draws neighbouring hexes beyond it to fill the other dimension.
    """
    vx,vy,wc,wr=window
    xs=[world_hex.center((x,y))[0] for x in (vx,vx+wc-1) for y in range(vy,vy+wr)]
    left,right=min(xs)-math.sqrt(3)/2+.45,max(xs)+math.sqrt(3)/2-.45
    top,bottom=1.5*vy-.5,1.5*(vy+wr-1)+.5
    r=min(cols/(right-left),rows/(bottom-top))
    ox,oy=(cols-(left+right)*r)/2,(rows-(top+bottom)*r)/2
    if bounds:
        # Keep the paper inside the world: no empty strip beyond its first/last row or column.
        w,h=bounds;s3=math.sqrt(3)
        for axis,low,high,size in ((0,.05,s3*(w-.5)-.05,cols),(1,-.5,1.5*(h-1)+.5,rows)):
            o=ox if axis==0 else oy;start,end=-o/r,(size-o)/r
            if end-start<=high-low:
                shift=low-start if start<low else high-end if end>high else 0
                if axis==0:ox-=shift*r
                else:oy-=shift*r
    return r,ox,oy


def sheet_cells(world,window,cols,rows):
    """World cells whose centre lies on the sheet (revealed on the atlas once solved)."""
    w,h=len(world[0]),len(world);out=[]
    r,ox,oy=geometry(window,cols,rows,(w,h));vx,vy,wc,wr=window
    for y in range(max(0,vy-3),min(h,vy+wr+3)):
        for x in range(max(0,vx-4),min(w,vx+wc+4)):
            px,py=world_hex.center((x,y),r,ox,oy)
            if 0<=px<=cols and 0<=py<=rows:out.append((x,y))
    return out


def target_point(state,target):
    """Target hex centre on the sheet, in piece units from the sheet's top-left corner."""
    r,ox,oy=geometry(state['window'],state['cols'],state['rows'],state.get('bounds'))
    return world_hex.center(tuple(target),r,ox,oy)


# ---------- torn edges (recomputed from the ID, not saved) ----------
def _tear(rng,a,b,amp,border):
    (ax,ay),(bx,by)=a,b;n=11
    nx,ny=-(by-ay),bx-ax;length=math.hypot(nx,ny) or 1
    at=.25+rng.random()*.5;lobe=0 if border else (rng.choice((-1,1))*(.06+rng.random()*.06))
    points=[a]
    for i in range(1,n):
        t=i/n;j=(rng.random()*2-1)*amp+lobe*math.exp(-((t-at)**2)/.012)
        points.append((ax+(bx-ax)*t+nx/length*j,ay+(by-ay)*t+ny/length*j))
    return points+[b]


def outlines(ident,cols,rows):
    """Torn polygon of every piece, relative to its centre, in piece units."""
    rng=random.Random('torn-map-edges:'+str(ident))
    def jitter(c,r):
        inner_x=0<c<cols;inner_y=0<r<rows
        return (c+((rng.random()*2-1)*.06 if inner_x and inner_y else (rng.random()*2-1)*.035 if inner_x else 0),
                r+((rng.random()*2-1)*.06 if inner_x and inner_y else (rng.random()*2-1)*.035 if inner_y else 0))
    v=[[jitter(c,r) for c in range(cols+1)] for r in range(rows+1)]
    horizontal=[[_tear(rng,v[r][c],v[r][c+1],.017 if r in (0,rows) else .033,r in (0,rows)) for c in range(cols)] for r in range(rows+1)]
    vertical=[[_tear(rng,v[r][c],v[r+1][c],.017 if c in (0,cols) else .033,c in (0,cols)) for c in range(cols+1)] for r in range(rows)]
    shapes=[]
    for gy in range(rows):
        for gx in range(cols):
            cx,cy=gx+.5,gy+.5;points=[]
            for line,reverse in ((horizontal[gy][gx],False),(vertical[gy][gx+1],False),
                                 (horizontal[gy+1][gx],True),(vertical[gy][gx],True)):
                line=line[::-1] if reverse else line
                points+=[(x-cx,y-cy) for x,y in line[:-1]]
            shapes.append(points)
    return shapes


# ---------- pieces on the table ----------
def turn(x,y,r):
    """Rotate a vector clockwise (screen axes) by r quarter turns."""
    for _ in range(r%4):x,y=-y,x
    return x,y


def generate(rng,settings,window,bounds=None):
    cols,rows=settings['cols'],settings['rows'];n=cols*rows;tw,th=TABLE
    k=math.ceil(math.sqrt(n*tw/th));kr=math.ceil(n/k)
    slots=list(range(k*kr));rng.shuffle(slots)
    pieces=[]
    for i in range(n):
        sx,sy=slots[i]%k,slots[i]//k
        pieces.append([round((sx+.5)*tw/k+(rng.random()*2-1)*.08,3),round((sy+.5)*th/kr+(rng.random()*2-1)*.07,3),
                       rng.randrange(4) if settings['rotate'] else 0,i])
    return dict(version=VERSION,cols=cols,rows=rows,rotate=bool(settings['rotate']),window=list(window),bounds=list(bounds) if bounds else None,pieces=pieces,glued=[])


def members(state,group):
    return [i for i,p in enumerate(state['pieces']) if p[3]==group]


def solved(state):
    return len({p[3] for p in state['pieces']})==1


def _clamp(state,group):
    tw,th=TABLE;ids=members(state,group);pieces=state['pieces']
    for axis,size in ((0,tw),(1,th)):
        low=min(pieces[i][axis] for i in ids);high=max(pieces[i][axis] for i in ids)
        shift=(size-low-high)/2 if high-low>size-1 else .5-low if low<.5 else size-.5-high if high>size-.5 else 0
        for i in ids:pieces[i][axis]+=shift


def _neighbour(state,i,dx,dy):
    cols,rows=state['cols'],state['rows'];gx,gy=i%cols+dx,i//cols+dy
    return gy*cols+gx if 0<=gx<cols and 0<=gy<rows else None


def _snap(state,group):
    """Glue the moved group to every true neighbour lying within the tolerance."""
    pieces=state['pieces'];joined=False;merged=True
    while merged:
        merged=False
        for a in members(state,group):
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                b=_neighbour(state,a,dx,dy)
                if b is None or pieces[b][3]==group or pieces[b][2]!=pieces[a][2]:continue
                ox,oy=turn(dx,dy,pieces[a][2])
                ex,ey=pieces[a][0]+ox,pieces[a][1]+oy
                if math.hypot(ex-pieces[b][0],ey-pieces[b][1])<SNAP:
                    sx,sy=pieces[b][0]-ex,pieces[b][1]-ey;other=pieces[b][3]
                    for i in members(state,group):pieces[i][0]+=sx;pieces[i][1]+=sy;pieces[i][3]=other
                    group=other;merged=joined=True;break
            if merged:break
    if joined:
        for a in members(state,group):
            for dx,dy in ((1,0),(0,1)):
                b=_neighbour(state,a,dx,dy)
                if b is not None and pieces[b][3]==group and [a,b] not in state['glued']:state['glued'].append([a,b])
    for p in pieces:p[0],p[1]=round(p[0],4),round(p[1],4)
    return joined


def assemble(state):
    """Lay the solved map upright in the middle of the table."""
    tw,th=TABLE;cols,rows=state['cols'],state['rows']
    for i,p in enumerate(state['pieces']):
        p[0]=round(tw/2+(i%cols+.5-cols/2),4);p[1]=round(th/2+(i//cols+.5-rows/2),4);p[2]=0


def move(state,i,x,y):
    """Move piece i's group so that piece i is centred at (x,y); returns True if it glued."""
    p=state['pieces'][i];dx,dy=x-p[0],y-p[1]
    for j in members(state,p[3]):state['pieces'][j][0]+=dx;state['pieces'][j][1]+=dy
    _clamp(state,p[3]);return _snap(state,p[3])


def rotate(state,i):
    """Turn piece i's group 90° clockwise around piece i; returns True if it glued."""
    p=state['pieces'][i];px,py=p[0],p[1]
    for j in members(state,p[3]):
        q=state['pieces'][j];dx,dy=turn(q[0]-px,q[1]-py,1)
        q[0],q[1],q[2]=px+dx,py+dy,(q[2]+1)%4
    _clamp(state,p[3]);return _snap(state,p[3])


def number(value):
    return type(value) in (int,float) and math.isfinite(value)
