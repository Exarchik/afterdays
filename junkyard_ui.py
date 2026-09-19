"""Draggable scrap layers backed by saved model coordinates, not UI-only progress."""
import tkinter as tk
from inspection_ui import window
from visuals import PANEL,TEXT,GOLD,icon
import progression as p
from i18n import t as tr

def show(app,ident):
    g=app.game;q=g.junk_quest(ident)
    if not q:return
    win=window(app,tr('scav.junkyard'))
    tk.Label(win,text=tr('scav.junk_help'),bg=PANEL,fg=TEXT,wraplength=570).pack(padx=12,pady=12)
    status=tk.Label(win,bg=PANEL,fg=GOLD);status.pack(pady=5)
    canvas=tk.Canvas(win,bg='#242b23',highlightthickness=0,height=440);canvas.pack(fill='both',expand=True,padx=10,pady=10)
    drag={}
    def scale():return max(1,canvas.winfo_width())/640,max(1,canvas.winfo_height())/440
    def draw(event=None):
        canvas.delete('all');sx,sy=scale()
        for obj in q['junk_objects']:
            if obj['found']:continue
            x,y,w,h=obj['x']*sx,obj['y']*sy,obj['w']*sx,obj['h']*sy
            if obj['kind']=='debris':
                colors=['#645d4a','#475852','#6b4d3e'];color=colors[obj['style']]
                canvas.create_rectangle(x,y,x+w,y+h,fill=color,outline='#a49470',width=2)
                if obj['style']==0:
                    for n in range(1,5):canvas.create_line(x+w*n/5,y+5,x+w*n/5,y+h-5,fill='#3b3a30',width=3)
                elif obj['style']==1:
                    canvas.create_oval(x+w*.2,y+h*.15,x+w*.8,y+h*.85,fill='#252d29',outline='#899080',width=5)
                else:
                    canvas.create_line(x+6,y+6,x+w-6,y+h-6,fill='#987e61',width=5)
                    canvas.create_line(x+6,y+h-6,x+w-6,y+6,fill='#987e61',width=5)
            else:
                canvas.create_rectangle(x,y,x+w,y+h,fill='#314b38',outline='#dfc986' if obj['kind']=='target' else '#8caf91',width=2)
                item=dict(kind='quest',name=tr('scav.junk_part'),rarity=0) if obj['kind']=='target' else p.ammunition(obj['ammo_type']) if obj['kind']=='ammo' else p.supply(obj['kind'])
                icon(canvas,item,x,y,min(w,h))
        status.config(text=tr('scav.junk_progress',count=q['progress'],goal=q['goal'])+(tr('scav.return_giver') if g.quest_ready(q) else ''))
    def press(event):
        sx,sy=scale();x,y=event.x/sx,event.y/sy;obj=g.junk_top(q,x,y)
        if not obj:return
        if obj['kind']=='debris':drag.update(id=obj['id'],dx=x-obj['x'],dy=y-obj['y'])
        elif g.junk_collect(ident,x,y):draw();app.refresh()
    def move(event):
        if not drag:return
        sx,sy=scale()
        if g.junk_move(ident,drag['id'],event.x/sx-drag['dx'],event.y/sy-drag['dy']):draw()
    canvas.bind('<Configure>',draw);canvas.bind('<Button-1>',press);canvas.bind('<B1-Motion>',move);canvas.bind('<ButtonRelease-1>',lambda e:drag.clear());draw()
