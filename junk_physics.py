"""Junkyard pile: top-down debris removed one piece at a time (mikado rule).

Pure geometry and generation, without Tk or a game instance. All state lives in the
quest dictionary: pieces, finds and the remaining stamina for this minigame.
"""
import hashlib
import math
import random

WIDTH,HEIGHT=850,560
VERSION=2
# name, stamina cost, width, height, colour
MATERIALS=[('Газети',1,110,78,'#a9aaa0'),
           ('Картон',1,140,92,'#a58d64'),
           ('Дошка',2,210,46,'#806044'),
           ('Мішок',3,120,96,'#647463'),
           ('Лист металу',5,180,112,'#6a7c7d'),
           ('Бетонна плита',8,170,128,'#82827b')]
HEAVY,LIGHT,FILLER=(3,4,5),(0,1,2,3),(0,1,2)
FIND_RADIUS=24
# Editor-tunable settings and their limits: (default, minimum, maximum).
SETTINGS={'parts':(3,1,6),'max_stamina':(30,10,100),'stamina_per_satiety':(3,1,10)}


def settings_for(spec):
    spec=spec or {}
    return {key:spec.get(key,default) for key,(default,_,_) in SETTINGS.items()}


def validate_settings(spec,prefix=''):
    return [f'{prefix}Некоректне поле {key}: ціле число від {low} до {high}'
            for key,(_,low,high) in SETTINGS.items()
            if key in spec and (type(spec[key]) is not int or not low<=spec[key]<=high)]


def corners(p):
    c,s=math.cos(p['a']),math.sin(p['a']);hw,hh=p['w']/2,p['h']/2
    return [(p['x']+x*c-y*s,p['y']+x*s+y*c) for x,y in ((-hw,-hh),(hw,-hh),(hw,hh),(-hw,hh))]


def octagon(f,radius=FIND_RADIUS):
    return [(f['x']+radius*math.cos(i*math.pi/4),f['y']+radius*math.sin(i*math.pi/4)) for i in range(8)]


def overlap(a,b):
    """Separating-axis test for two convex polygons; touching edges do not overlap."""
    for poly in (a,b):
        for i,(x1,y1) in enumerate(poly):
            x2,y2=poly[(i+1)%len(poly)];nx,ny=y2-y1,x1-x2
            pa=[x*nx+y*ny for x,y in a];pb=[x*nx+y*ny for x,y in b]
            if max(pa)<=min(pb)+.5 or max(pb)<=min(pa)+.5:return False
    return True


def inside(x,y,poly):
    result=False;j=len(poly)-1
    for i,(xi,yi) in enumerate(poly):
        xj,yj=poly[j]
        if (yi>y)!=(yj>y) and x<(xj-xi)*(y-yi)/(yj-yi)+xi:result=not result
        j=i
    return result


def live(q):return [p for p in q['junk_pieces'] if not p['gone']]


def blockers(q,piece):
    """Pieces lying on top of this one; it can be taken only when the list is empty."""
    poly=corners(piece)
    return [p for p in live(q) if p['z']>piece['z'] and overlap(poly,corners(p))]


def find_free(q,find):
    poly=octagon(find)
    return not any(overlap(poly,corners(p)) for p in live(q))


def peek(q,find):
    """A visible point on the rim of a partly covered find, used for the glint."""
    ring=[(find['x']+FIND_RADIUS*math.cos(i*math.pi/6),find['y']+FIND_RADIUS*math.sin(i*math.pi/6)) for i in range(12)]
    polys=[corners(p) for p in live(q)]
    free=[pt for pt in ring if not any(inside(*pt,poly) for poly in polys)]
    return free[0] if free and len(free)<len(ring) else None


def piece_at(q,x,y):
    return next((p for p in sorted(live(q),key=lambda p:-p['z']) if inside(x,y,corners(p))),None)


def find_at(q,x,y):
    return next((f for f in q['junk_finds'] if not f['found'] and math.hypot(x-f['x'],y-f['y'])<=FIND_RADIUS+2),None)


def seed_for(q):
    return int.from_bytes(hashlib.sha256((q['id']+':pile').encode()).digest()[:4],'big')


def build(q,targets,bonus=()):
    """Create a pile: every find sits under a heavy piece and one or two lighter ones."""
    rng=random.Random(seed_for(q))
    count=len(targets)+len(bonus)
    spots=[]
    columns=max(3,math.ceil(count/2))
    for row in range(2):
        for col in range(columns):
            spots.append((WIDTH*(col+.5)/columns+rng.uniform(-30,30),165+row*230+rng.uniform(-25,25)))
    rng.shuffle(spots)
    finds=[]
    for n,kind in enumerate(list(targets)+list(bonus)):
        x,y=spots[n];entry=dict(id=f'find{n}',kind=kind if isinstance(kind,str) else kind['kind'],x=round(x,1),y=round(y,1),found=False)
        if not isinstance(kind,str):entry.update({k:v for k,v in kind.items() if k!='kind'})
        finds.append(entry)
    pieces=[]
    def add(x,y,material):
        name,cost,w,h,_=MATERIALS[material]
        x=max(40,min(WIDTH-40,x));y=max(40,min(HEIGHT-40,y))
        pieces.append(dict(id=f'piece{len(pieces)}',material=material,x=round(x,1),y=round(y,1),w=w,h=h,
                           a=round(rng.uniform(-.7,.7),3),z=len(pieces),gone=False))
    for f in finds:add(f['x']+rng.uniform(-15,15),f['y']+rng.uniform(-15,15),rng.choice(HEAVY))
    for _ in range(9):add(rng.uniform(110,WIDTH-110),rng.uniform(100,HEIGHT-100),rng.randrange(len(MATERIALS)))
    for f in finds:
        add(f['x']+rng.uniform(-35,35),f['y']+rng.uniform(-25,25),rng.choice(LIGHT))
        if rng.random()<.6:add(f['x']+rng.uniform(-45,45),f['y']+rng.uniform(-30,30),rng.choice(FILLER))
    for _ in range(5):add(rng.uniform(110,WIDTH-110),rng.uniform(100,HEIGHT-100),rng.choice(FILLER))
    q.update(junk_pieces=pieces,junk_finds=finds,junk_version=VERSION)
    q.pop('junk_objects',None);q.pop('junk_physics',None)
