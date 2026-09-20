"""One deterministic nearest-next-station chain, clipped by explored map cells."""
import math

def station_order(game):
    from frontier import METRO_CITIES
    order=[0];remaining=set(METRO_CITIES)-{0}
    while remaining:
        nxt=min(remaining,key=lambda n:(math.dist(game.cities[order[-1]],game.cities[n]),n))
        order.append(nxt);remaining.remove(nxt)
    return order

def visible_segments(a,b,revealed):
    steps=max(1,math.ceil(max(abs(b[0]-a[0]),abs(b[1]-a[1]))*8));start=None
    def point(t):return (a[0]+.5+(b[0]-a[0])*t,a[1]+.5+(b[1]-a[1])*t)
    for n in range(steps):
        mid=point((n+.5)/steps);visible=revealed(math.floor(mid[0]),math.floor(mid[1]))
        if visible and start is None:start=point(n/steps)
        if start is not None and (not visible or n==steps-1):
            yield (*start,*point((n if not visible else n+1)/steps));start=None

def draw(canvas,game,t,ox,oy,revealed=None):
    revealed=revealed or game.revealed;order=station_order(game)
    for a,b in zip(order,order[1:]):
        bright=all(n in game.known_cities and n in game.metro_unlocked for n in (a,b))
        for x,y,xx,yy in visible_segments(game.cities[a],game.cities[b],revealed):
            canvas.create_line(ox+x*t,oy+y*t,ox+xx*t,oy+yy*t,fill='#58d9d1' if bright else '#47615d',width=3,dash=(7,4))
    for n in order:
        x,y=game.cities[n]
        if not revealed(x,y):continue
        px,py=ox+(x+.5)*t,oy+(y+.5)*t;color='#58d9d1' if n in game.metro_unlocked else '#658079'
        canvas.create_oval(px-7,py-7,px+7,py+7,fill='#173b3a',outline=color,width=2)
        canvas.create_text(px,py,text='M',fill=color,font=('Segoe UI',8,'bold'))
