"""Compact status bars, location menus and travelling scribe quest cards."""
import tkinter as tk
from tkinter import ttk
import game_dialogs as messagebox
import progression as p
from i18n import t as tr
from visuals import PANEL,TEXT,GOLD

class Tooltip:
    def __init__(self,widget,text):
        """Attach a transient explanation to an icon or progress bar."""
        self.widget=widget;self.text=text;self.win=None
        widget.bind('<Enter>',self.show,add='+');widget.bind('<Leave>',self.hide,add='+');widget.bind('<Destroy>',self.hide,add='+')
    def show(self,event=None):
        """Display the current explanation next to the hovered widget."""
        self.hide();self.win=tk.Toplevel(self.widget);self.win.overrideredirect(True)
        self.win.geometry(f'+{self.widget.winfo_rootx()+8}+{self.widget.winfo_rooty()+self.widget.winfo_height()+3}')
        tk.Label(self.win,text=self.text() if callable(self.text) else self.text,bg='#15241d',fg=TEXT,padx=8,pady=5).pack()
    def hide(self,event=None):
        """Remove the tooltip on leave or widget destruction."""
        if self.win:
            self.win.destroy();self.win=None

class StatusBar(tk.Frame):
    def __init__(self,parent):
        """Build health/experience bars and icon-only stat labels with tooltips."""
        super().__init__(parent,bg=PANEL);self.game=None;self.fields={}
        for key,symbol in [('hp','♥'),('xp','★'),('level','◈'),('defense','⛨'),('weight','⚖'),('money','¤'),('turn','◷'),('coward','⚑')]:
            frame=tk.Frame(self,bg=PANEL);frame.pack(side='left',fill='x',expand=key in ('hp','xp'),padx=5,pady=7)
            icon=tk.Label(frame,text=symbol,bg=PANEL,fg=GOLD,font=('Segoe UI',13));icon.pack(side='left')
            if key in ('hp','xp'):
                w=tk.Canvas(frame,width=150,height=23,bg='#17231d',highlightthickness=0);w.pack(side='left',fill='x',expand=True)
                w.bind('<Configure>',lambda e:self.refresh(self.game) if self.game else None)
            else:
                w=tk.Label(frame,bg=PANEL,fg=TEXT);w.pack(side='left')
            self.fields[key]=w
            for target in (icon,w):Tooltip(target,lambda key=key:tr('update032.stat_'+key))
    def refresh(self,g):
        """Render current numeric values; XP progress is relative to the current level."""
        self.game=g
        start=p.xp_for_level(g.level);goal=p.xp_for_level(g.level+1)
        for key,amount,total,color in [('hp',g.hp,g.max_hp,'#4fa86e'),('xp',g.xp-start,goal-start,'#c9ae41')]:
            c=self.fields[key];width=max(1,c.winfo_width());c.delete('all')
            c.create_rectangle(0,0,width*min(1,max(0,amount/max(1,total))),23,fill=color,outline='')
            c.create_text(width/2,11,text=f'{amount}/{total}',fill='#fff3d9',font=('Segoe UI',9,'bold'))
        for key,value in [('level',g.level),('defense',g.defense),('weight',f'{g.weight:.1f}/{g.capacity:g}'),('money',g.money),('turn',g.turn),('coward',g.coward_turns or '—')]:self.fields[key].config(text=str(value))

def scribe(app):
    if not app.game.scribe:return
    from refinement_ui import QuestCards
    win=app.popup(tr('update032.scribe'),'750x670');QuestCards(win,app,mayor=True).pack(fill='both',expand=True)

def map_context(app,event):
    if app.game.battle:
        import inspection_ui
        return inspection_ui.inspect_monster(app,event)
    g=app.game;x,y=app.cell(event)
    if not 0<=x<len(g.world[0]) or not 0<=y<len(g.world):return
    app.route.pause();menu=tk.Menu(app.canvas,tearoff=False,bg=PANEL,fg=TEXT)
    known=app.map_revealed(x,y)
    if not known:
        menu.add_command(label=tr('update032.unknown'),state='disabled')
    else:
        import afterdays as r
        city=next((n for n,pos in enumerate(g.cities) if pos==[x,y]),None)
        title=g.city_name(city) if city is not None else r.TERRAINS[g.world[y][x]][1]
        info=f'{title} · ({x}, {y}) · L{g.region_at(x,y)}'
        if city is not None:info+='\n'+tr('reputation.status',value=g.reputation(city),buy=round((__import__('reputation').buy_factor(g.reputation(city))-1)*100),sell=round((__import__('reputation').sell_factor(g.reputation(city))-1)*100))
        menu.add_command(label=tr('update032.location_info'),command=lambda:messagebox.showinfo(title,info,parent=app.root))
        if (x,y)!=(g.x,g.y) and g.passable(x,y):menu.add_command(label=tr('update032.go'),command=lambda:app.route.set_target((x,y)))
        if (x,y)==(g.x,g.y):
            menu.add_command(label=tr('update032.local'),command=lambda:app.tabs.select(0))
            if not g.road_event:
                if g.regular_city:menu.add_command(label=tr('update032.sleep'),command=lambda:app.act(g.rest))
                else:menu.add_command(label=tr('update032.search'),command=lambda:app.act(g.search))
            if city in g.mayors or g.regular_city:menu.add_command(label=tr('update032.quests'),command=app.mayor)
        menu.add_command(label=tr('update032.atlas'),command=app.atlas)
    try:menu.tk_popup(event.x_root,event.y_root)
    finally:menu.grab_release()
    return 'break'
