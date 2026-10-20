"""Shotgun cone: six pellets fly in a fan and hit whatever stands in their way.

Geometry works in an undistorted flat-top hex plane where neighbouring centres are one
unit apart, so the cone matches what the arena shows (the screen only squashes it).
Each pellet leaves at a random angle within ±spread (triangular, denser in the middle),
takes the first hostile body it crosses, stops at a wall or at the end of the range.
Damage keeps the 1/6-of-a-shell split and falls off beyond two hexes.
"""
import math
import random

import hexgrid

PELLETS=6
SPREAD=24          # default half-angle of the fan, degrees (item field `spread` overrides)
FALLOFF=40         # % of damage left at the end of the range (item field `falloff` overrides)
FULL=2             # hexes of full damage
BODY=.39           # radius of a unit's body; neighbours are 1 apart
KNOCKBACK=4        # pellets into an adjacent enemy that push it one hex back
STEP=.08
SQ3=math.sqrt(3)/2


def point(pos):
    q,r=pos
    return SQ3*q,r+q/2


def axial(x,y):
    q=x/SQ3
    return q,y-q/2


def is_shotgun(weapon):
    from game.systems.combat import category
    return bool(weapon) and category(weapon)=='shotgun'


def field(weapon,key,default):
    """Item value, else the model's value in data/equipment.json, else the default."""
    if key in weapon:return weapon[key]
    import content
    return content.EQUIPMENT.get(weapon.get('type_id'),{}).get(key,default)


def spread(game,weapon,chance):
    """Half-angle in radians: the item's spread, narrowed by the shooter's accuracy."""
    base=field(weapon,'spread',SPREAD)
    return math.radians(base*(1.4-.6*max(0,min(100,chance))/100))


def falloff(weapon,distance,limit):
    floor=field(weapon,'falloff',FALLOFF)/100
    if distance<=FULL:return 1.
    return max(floor,1-(1-floor)*(distance-FULL)/max(1,limit-FULL))


def aim(source,target):
    (sx,sy),(tx,ty)=point(source),point(target)
    return math.atan2(ty-sy,tx-sx)


def bodies(game):
    b=game.battle
    hostile=getattr(game,'hostile_to_player',None)
    return [(e,point(e['pos'])) for e in b['enemies'] if e['hp']>0 and (hostile is None or hostile(e))]


def trace(game,angle,limit,units=None,walls=None):
    """One pellet: returns (enemy or None, end point in axial floats, distance, hit_wall)."""
    b=game.battle;sx,sy=point(b['pos']);dx,dy=math.cos(angle),math.sin(angle)
    reach=limit+.45;best=None;hit=None
    for enemy,(ex,ey) in (units if units is not None else bodies(game)):
        # Ray–circle entry point.
        fx,fy=ex-sx,ey-sy;along=fx*dx+fy*dy
        if along<=0:continue
        miss=fx*fx+fy*fy-along*along
        if miss>BODY*BODY:continue
        t=along-math.sqrt(BODY*BODY-miss)
        if t<=reach and (best is None or t<best):best,hit=t,enemy
    end=best if best is not None else reach
    walls=walls if walls is not None else set(map(tuple,b['walls']));t=.5
    while t<end:
        cell=hexgrid.rounded(*axial(sx+dx*t,sy+dy*t))
        if cell in walls or not (0<=cell[0]<b['w'] and 0<=cell[1]<b['h']):
            return None,list(axial(sx+dx*t,sy+dy*t)),t,True
        t+=STEP
    return hit,list(axial(sx+dx*end,sy+dy*end)),end,False


def fan(game,target,chance,rng,limit,weapon,wild=False):
    """Pellet results for one shell aimed at the target's centre."""
    angle=aim(game.battle['pos'],target['pos']);half=spread(game,weapon,chance)
    if wild:angle+=rng.uniform(-1,1)*half*1.5;half*=1.5
    units=bodies(game);walls=set(map(tuple,game.battle['walls']))
    return [trace(game,angle+(rng.random()+rng.random()-1)*half,limit,units,walls) for _ in range(PELLETS)]


def expected(game,target,chance,limit,weapon,samples=240):
    """Average pellets and damage share per enemy id, for the hover preview (own RNG)."""
    rng=random.Random(0);angle=aim(game.battle['pos'],target['pos']);half=spread(game,weapon,chance)
    units=bodies(game);walls=set(map(tuple,game.battle['walls']));result={}
    for _ in range(samples):
        enemy,_,distance,_=trace(game,angle+(rng.random()+rng.random()-1)*half,limit,units,walls)
        if enemy is None:continue
        n,share=result.get(enemy['id'],(0,0))
        result[enemy['id']]=(n+PELLETS/samples,share+PELLETS/samples*falloff(weapon,distance,limit)/PELLETS)
    return result


def cone(game,target,chance,limit,weapon,steps=10):
    """Outline of the fan as axial points (for drawing): apex then the far arc."""
    sx,sy=point(game.battle['pos']);angle=aim(game.battle['pos'],target['pos'])
    half=spread(game,weapon,chance);reach=limit+.45
    arc=[axial(sx+math.cos(angle-half+2*half*i/steps)*reach,sy+math.sin(angle-half+2*half*i/steps)*reach) for i in range(steps+1)]
    return [axial(sx,sy)]+arc


def knockback(game,enemy):
    """Push an adjacent enemy one hex straight back if that hex is free floor."""
    b=game.battle;px,py=b['pos'];ex,ey=enemy['pos']
    if hexgrid.distance(b['pos'],enemy['pos'])!=1:return None
    dest=(2*ex-px,2*ey-py)
    taken={tuple(e['pos']) for e in b['enemies'] if e is not enemy}|set(map(tuple,b['walls']))|{tuple(b['pos'])}
    if not (0<=dest[0]<b['w'] and 0<=dest[1]<b['h']) or dest in taken:return None
    return list(dest)
