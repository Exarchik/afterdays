"""Junkyard pile: top-down debris removed one piece at a time (mikado rule).

Pure geometry and generation, without Tk or a game instance. All state lives in the
quest dictionary: pieces, finds and the work done since satiety was last spent.
Lifting costs the player's satiety: every `work_per_satiety` points of lifted weight take
one point. After `settle_min`–`settle_max` points of removed weight the pile may settle:
a new piece slides in on top or between the existing layers.
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
# Accusative names for «… прибрано».
ACCUSATIVE=('Газети','Картон','Дошку','Мішок','Лист металу','Бетонну плиту')
HEAVY,LIGHT,FILLER=(3,4,5),(0,1,2,3),(0,1,2)
SETTLE=(0,0,1,1,2,3,3,4)  # mostly light debris slides in when the pile settles
FIND_RADIUS=24
# Editor-tunable settings and their limits: (default, minimum, maximum).
SETTINGS={'parts':(3,1,6),'work_per_satiety':(4,2,8),'settle_min':(15,5,40),'settle_max':(20,5,60),'settle_chance':(60,0,100)}


def settings_for(spec):
    spec=spec or {}
    return {key:spec.get(key,default) for key,(default,_,_) in SETTINGS.items()}


def validate_settings(spec,prefix=''):
    errors=[f'{prefix}Некоректне поле {key}: ціле число від {low} до {high}'
            for key,(_,low,high) in SETTINGS.items()
            if key in spec and (type(spec[key]) is not int or not low<=spec[key]<=high)]
    values=settings_for(spec)
    if not errors and values['settle_min']>values['settle_max']:
        errors.append(f'{prefix}Осідання: «від» не може бути більше за «до»')
    return errors


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


def settle_rng(q):
    """Deterministic per quest and per settle, independent of the game's own RNG."""
    return random.Random(f"{q['id']}:settle:{q.get('junk_settles',0)}")


def next_settle(q,rng):
    s=q['junk_settings'];q['junk_since']=0
    q['junk_settle_at']=rng.randint(s['settle_min'],max(s['settle_min'],s['settle_max']))


def settle(q,rng):
    """A new piece slides in on top of the pile or between its layers; returns (piece, between)."""
    material=rng.choice(SETTLE);name,cost,w,h,_=MATERIALS[material]
    hidden=[f for f in q['junk_finds'] if not f['found']]
    if hidden and rng.random()<.6:
        f=rng.choice(hidden);x,y=f['x']+rng.uniform(-60,60),f['y']+rng.uniform(-45,45)
    else:x,y=rng.uniform(110,WIDTH-110),rng.uniform(100,HEIGHT-100)
    pieces=sorted(live(q),key=lambda p:p['z'])
    between=len(pieces)>2 and rng.random()<.5
    piece=dict(id=f"piece{len(q['junk_pieces'])}",material=material,x=round(max(50,min(WIDTH-50,x)),1),
               y=round(max(50,min(HEIGHT-50,y)),1),w=w,h=h,a=round(rng.uniform(-.8,.8),3),gone=False)
    at=int(len(pieces)*(.3+rng.random()*.5)) if between else len(pieces)
    pieces.insert(at,piece)
    for z,p in enumerate(pieces):p['z']=z
    q['junk_pieces'].append(piece)
    return piece,between
