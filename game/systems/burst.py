"""Automatic burst: five bullets in quick succession, each a little wider (recoil).

Uses the shotgun's ballistics (see shotgun.py): a bullet takes the first hostile body on
its way and stops at a wall; there is no separate hit roll. The first bullet flies close to
the aim line, every next one gets a wider random deviation. The shooter's hit chance
(which already includes the burst penalty) narrows the whole fan. No range falloff.
"""
import math
import random

from game.systems import shotgun

BULLETS=5
BASE=3.     # half-angle of the first bullet, degrees
CLIMB=3.5   # extra half-angle per following bullet, degrees


def half(i,chance):
    return math.radians((BASE+CLIMB*i)*(1.4-.6*max(0,min(100,chance))/100))


def volley(game,target,chance,rng,limit,wild=False):
    """Traces of the five bullets; a misfire throws the burst off the aim line."""
    angle=shotgun.aim(game.battle['pos'],target['pos'])
    widen=1.5 if wild else 1
    if wild:angle+=rng.uniform(-1,1)*half(BULLETS-1,chance)
    units=shotgun.bodies(game);walls=set(map(tuple,game.battle['walls']))
    return [shotgun.trace(game,angle+(rng.random()+rng.random()-1)*half(i,chance)*widen,limit,units,walls) for i in range(BULLETS)]


def expected(game,target,chance,limit,samples=80):
    """Average bullets per enemy id (own RNG, never touches the game's)."""
    rng=random.Random(0);angle=shotgun.aim(game.battle['pos'],target['pos'])
    units=shotgun.bodies(game);walls=set(map(tuple,game.battle['walls']));result={}
    for _ in range(samples):
        for i in range(BULLETS):
            enemy=shotgun.trace(game,angle+(rng.random()+rng.random()-1)*half(i,chance),limit,units,walls)[0]
            if enemy is not None:result[enemy['id']]=result.get(enemy['id'],0)+1/samples
    return result


def cone(game,target,chance,limit,bullet=BULLETS-1,steps=8):
    """Outline (axial points) of the fan reached by the given bullet of the burst."""
    sx,sy=shotgun.point(game.battle['pos']);angle=shotgun.aim(game.battle['pos'],target['pos'])
    h=half(bullet,chance);reach=limit+.45
    return [shotgun.axial(sx,sy)]+[shotgun.axial(sx+math.cos(angle-h+2*h*i/steps)*reach,sy+math.sin(angle-h+2*h*i/steps)*reach) for i in range(steps+1)]
