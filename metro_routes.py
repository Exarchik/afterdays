import world_hex
"""One deterministic nearest-next-station chain, clipped by explored map cells."""
import math

def station_order(game):
    from game.systems.frontier import METRO_CITIES
    order=[0];remaining=set(METRO_CITIES)-{0}
    while remaining:
        nxt=min(remaining,key=lambda n:(world_hex.distance(game.cities[order[-1]],game.cities[n]),n))
        order.append(nxt);remaining.remove(nxt)
    return order

def visible_segments(a,b,revealed):
    """Segments in unit-radius hex screen coordinates, clipped to revealed cells."""
    pa,pb=world_hex.center(a),world_hex.center(b)
    steps=max(1,world_hex.distance(a,b)*8);start=None
    def point(t):return tuple(pa[i]+(pb[i]-pa[i])*t for i in (0,1))
    for n in range(steps):
        shown=revealed(*world_hex.cell(*point((n+.5)/steps)))
        if shown and start is None:start=point(n/steps)
        if start is not None and (not shown or n==steps-1):
            yield (*start,*point((n if not shown else n+1)/steps));start=None


def draw(canvas,game,t,ox,oy,revealed=None):
    from world_map import View,draw_metro
    draw_metro(canvas,game,View(t/2,ox,oy,0,0,len(game.world[0]),len(game.world)),revealed or game.revealed)
