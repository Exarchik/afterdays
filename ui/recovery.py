"""Small map markers and a grave inventory using the existing item renderer."""
import tkinter as tk
from tkinter import ttk

def draw_markers(canvas,game,t,ox,oy,revealed,point=None):
    x,y=game.respawn_pos
    if revealed(x,y):
        px,py=point((x,y)) if point else (ox+(x+.5)*t,oy+(y+.5)*t)
        px+=.33*t;py-=.38*t;size=max(5,min(13,t*.38))
        canvas.create_line(px,py,px,py+size*1.4,fill='#78e89a',width=2,tags='respawn_flag')
        canvas.create_polygon(px,py,px+size,py+size*.3,px,py+size*.65,fill='#49cc77',outline='#a4f3ba',tags='respawn_flag')
    for grave in game.graves:
        x,y=grave['pos']
        if not revealed(x,y):continue
        px,py=point((x,y)) if point else (ox+(x+.5)*t,oy+(y+.5)*t)
        s=max(5,min(16,t*.36))
        canvas.create_oval(px-s*.65,py-s,px+s*.65,py,fill='#aeb6b3',outline='#dae3dc',tags='grave_marker')
        canvas.create_rectangle(px-s*.65,py-s*.45,px+s*.65,py+s*.7,fill='#aeb6b3',outline='#dae3dc',tags='grave_marker')
        canvas.create_line(px,py-s*.4,px,py+s*.4,fill='#34443b',width=2,tags='grave_marker')
        canvas.create_line(px-s*.3,py-s*.1,px+s*.3,py-s*.1,fill='#34443b',width=2,tags='grave_marker')

def show(app):
    from ui.inspection import window, item_text
    from visuals import ItemGrid,PANEL,TEXT
    from ui.refinement import Detail
    g=app.game
    if g.battle or not g.local_graves():return
    win=window(app,'Надгробок — залишені речі')
    tk.Label(win,text='Заберіть речі. Те, що не вміститься в рюкзак, залишиться тут.',bg=PANEL,fg=TEXT,wraplength=600).pack(pady=8)
    detail=Detail(win,height=8)
    def selected(ident):
        item=next((i for grave in g.local_graves() for i in grave['items'] if i['id']==ident),None)
        detail.config(text=item_text(g,item) if item else '')
    grid=ItemGrid(win,selected,height=240);grid.pack(fill='both',expand=True,padx=8)
    detail.pack(fill='x',padx=8,pady=8)
    status=tk.StringVar();ttk.Label(win,textvariable=status).pack(fill='x',padx=8)
    def refresh():
        items=[i for grave in g.local_graves() for i in grave['items']];grid.set_items(items)
        status.set(f'Залишилося предметів: {len(items)} · Вага: {g.weight:.1f}/{g.capacity:g}')
        app.refresh()
    def collect(all_items=False):
        if all_items:g.collect_all_graves()
        else:
            ident=grid.selection
            grave=next((v for v in g.local_graves() if any(i['id']==ident for i in v['items'])),None)
            if grave:g.collect_grave(grave['id'],ident)
        detail.config(text='');refresh()
    bar=ttk.Frame(win);bar.pack(fill='x',padx=8,pady=6)
    ttk.Button(bar,text='Забрати вибране',command=collect).pack(side='left')
    ttk.Button(bar,text='Забрати все',command=lambda:collect(True)).pack(side='right')
    refresh()
