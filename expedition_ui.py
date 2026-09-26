"""Area boundaries and visited/searched cells; never expose hidden targets."""
def draw_search_areas(canvas,game,t,ox,oy,viewport=None):
    draw_defense_areas(canvas,game,t,ox,oy,viewport)
    for q in game.quests:
        if q['status']!='active' or not q.get('area') or game.quest_ready(q):continue
        a,b,c,d=q['area']
        if viewport:
            x,y,w,h=viewport;a=max(a,x);b=max(b,y);c=min(c,x+w-1);d=min(d,y+h-1)
        if a>c or b>d:continue
        color='#8bc4e4' if q['kind']=='scout' else '#99dd9f'
        canvas.create_rectangle(ox+a*t,oy+b*t,ox+(c+1)*t,oy+(d+1)*t,outline=color,width=3,dash=(5,3))
        for x,y in q.get('visited_cells',[]) if q['kind']=='scout' else q.get('searched_cells',[]):
            if a<=x<=c and b<=y<=d:canvas.create_text(ox+(x+.5)*t,oy+(y+.5)*t,text='✓' if q['kind']=='scout' else '×',fill=color)


def defense_cells(game,q):
    """Return cells where the active settlement-defense contract counts kills."""
    cx,cy=game.cities[q['city']]
    return {(x,y) for y in range(max(0,cy-10),min(len(game.world),cy+11))
            for x in range(max(0,cx-10),min(len(game.world[0]),cx+11)) if (x-cx)**2+(y-cy)**2<=100}

def draw_defense_areas(canvas,game,t,ox,oy,viewport=None):
    """Outline active defense zones on the overworld and atlas without revealing terrain."""
    for q in game.quests:
        if q.get('kind')!='hunt' or q.get('status')!='active' or game.quest_ready(q):continue
        cells=defense_cells(game,q)
        for x,y in cells:
            if viewport and not (viewport[0]<=x<viewport[0]+viewport[2] and viewport[1]<=y<viewport[1]+viewport[3]):continue
            for dx,dy,edge in ((0,-1,(x,y,x+1,y)),(0,1,(x,y+1,x+1,y+1)),(-1,0,(x,y,x,y+1)),(1,0,(x+1,y,x+1,y+1))):
                if (x+dx,y+dy) in cells:continue
                a,b,c,d=edge
                canvas.create_line(ox+a*t,oy+b*t,ox+c*t,oy+d*t,fill='#e5b75b',width=2,dash=(5,3),tags='defense_area')
