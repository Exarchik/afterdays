"""Area boundaries and visited/searched cells; never expose hidden targets."""
def draw_search_areas(canvas,game,t,ox,oy,viewport=None):
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
