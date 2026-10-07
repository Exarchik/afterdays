"""Shared seven-cell quest zones: center plus its six world neighbours."""
import world_hex


def around(pos):
    return (tuple(pos),)+world_hex.adjacent(pos)


def cells(q):
    a,b,c,d=q['area']
    return around(((a+c)//2,(b+d)//2))


def contains(q,x,y):
    return (x,y) in cells(q)


def migrate(q):
    """Convert old square-zone progress and targets once, without rerolling RNG."""
    if not q.get('area') or q.get('area_shape')=='hex7':return
    zone=cells(q);allowed=set(zone)
    completed=q.get('progress',0)>=q.get('goal',1)
    for key in ('visited_cells','searched_cells'):
        if key in q:q[key]=[list(p) for p in dict.fromkeys(map(tuple,q[key])) if p in allowed]
    if q.get('kind')=='scout' and not q.get('metro_chain'):
        q['goal']=7
        if completed:q['visited_cells']=list(map(list,zone))
        q['progress']=len(q.get('visited_cells',[]))
    for key in ('relic_pos','cache_pos'):
        if key in q and tuple(q[key]) not in allowed:
            searched=set(map(tuple,q.get('searched_cells',[])))
            target=next((p for p in zone if p not in searched),zone[0])
            q[key]=list(target)
            if not completed:q['searched_cells']=[p for p in q.get('searched_cells',[]) if tuple(p)!=target]
    q['area_shape']='hex7'


def migrate_game(game):
    for q in game.quests:
        chain=q.get('metro_chain')
        if chain:
            for step in chain['steps']:migrate(step)
            # The parent only mirrors the current stage; it is not a scout zone.
        else:migrate(q)
