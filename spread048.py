"""Allocate a fixed volley before resolving hits; one projectile, one target."""
import math
import hexgrid


def candidates(game,target):
    from combat033 import behind
    import progression as p
    source=game.battle['pos'];limit=p.mr.weapon_stats(game,game.weapon)['range']
    def point(a):return a[0]+a[1]*.5,a[1]*math.sqrt(3)/2
    sx,sy=point(source);tx,ty=point(target['pos']);dx,dy=tx-sx,ty-sy
    result=[]
    for enemy in game.battle['enemies']:
        pos=enemy['pos'];x,y=point(pos)
        if enemy is target or not game.hostile_to_player(enemy):continue
        if (x-sx)*dx+(y-sy)*dy<=0:continue
        if hexgrid.distance(source,pos)>limit or not hexgrid.visible(tuple(source),tuple(pos),game.battle['walls']):continue
        if hexgrid.distance(target['pos'],pos)<=1 or behind(source,target['pos'],pos):result.append(enemy)
    return result


def allocate(game,target,count,shotgun=False,burst=False):
    others=candidates(game,target) if shotgun or burst else []
    if not others:return [target]*count
    diverted=game.rng.choice((2,3)) if shotgun else 2
    game.rng.shuffle(others)
    result=[target]*(count-diverted)+[others[n%len(others)] for n in range(diverted)]
    # Interleave secondary bullets through the burst rather than always firing last.
    if burst:game.rng.shuffle(result)
    return result
