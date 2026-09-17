"""Same cell-edge fence geometry in the world view and schematic atlas."""
def draw_border(canvas,game,t,ox,oy,revealed,viewport=(0,0,48,32)):
    vx,vy,w,h=viewport
    for a,b in game.border_edges():
        if not any(vx<=x<vx+w and vy<=y<vy+h for x,y in (a,b)):continue
        if not (revealed(*a) or revealed(*b)):continue
        x,y=a
        if b[0]!=x:line=(ox+(x+1)*t,oy+y*t,ox+(x+1)*t,oy+(y+1)*t)
        else:line=(ox+x*t,oy+(y+1)*t,ox+(x+1)*t,oy+(y+1)*t)
        canvas.create_line(*line,fill='#000000',width=2,dash=(4,3))
        if game.checkpoint(a,b):
            mx,my=(line[0]+line[2])/2,(line[1]+line[3])/2
            size=max(3,t*.16);color='#79bd83' if game.border_open else '#d47554'
            canvas.create_rectangle(mx-size,my-size,mx+size,my+size,fill=color,outline='#111111',width=2)
