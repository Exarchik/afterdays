"""Public quest destinations; never route to a hidden cache/relic position."""
import math


def destination(game,quest):
    if not quest or quest.get('status')!='active':return None
    if game.quest_ready(quest):return game.quest_return_pos(quest)
    if quest.get('metro_chain'):return game.metro_step(quest).get('pos')
    return quest.get('pos')


def edge_arrow(view,target,origin):
    """Intersect a direction ray with the inset bounds of the displayed hex map."""
    cells=[(x,y) for x in (view.vx,view.vx+view.cols-1) for y in range(view.vy,view.vy+view.rows)]
    points=[view.point(p) for p in cells];r=view.radius
    left=min(x for x,y in points)-r*.866+8;right=max(x for x,y in points)+r*.866-8
    top=min(y for x,y in points)-r+8;bottom=max(y for x,y in points)+r-8
    ox,oy=view.point(origin);ox=max(left,min(right,ox));oy=max(top,min(bottom,oy))
    tx,ty=view.point(target);dx,dy=tx-ox,ty-oy
    length=math.hypot(dx,dy)
    if not length:return None
    limits=[]
    if dx:limits.append(((right if dx>0 else left)-ox)/dx)
    if dy:limits.append(((bottom if dy>0 else top)-oy)/dy)
    t=min(v for v in limits if v>=0);x,y=ox+dx*t,oy+dy*t;ux,uy=dx/length,dy/length
    return (x,y,x-ux*12-uy*6,y-uy*12+ux*6,x-ux*12+uy*6,y-uy*12-ux*6)
