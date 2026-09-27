"""Storm footprints shared by the world map and schematic atlas."""

def draw_storm(canvas,game,t,ox,oy,revealed):
    cells=game.storm_cells()
    for x,y in cells:
        if not revealed(x,y):continue
        canvas.create_rectangle(ox+x*t,oy+y*t,ox+(x+1)*t,oy+(y+1)*t,fill='#bad657',stipple='gray50',outline='#dfeb77',tags='storm')
    if game.storm:
        x,y=game.storm['pos']
        if revealed(x,y):canvas.create_text(ox+(x+.5)*t,oy+(y+.5)*t,text='☢',fill='#f3f5ad',font=('Segoe UI',max(8,int(t*.45)),'bold'),tags='storm')
