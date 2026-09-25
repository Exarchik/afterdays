"""Current weapon and remaining action points, visible during combat only."""
import tkinter as tk
from tkinter import ttk
import sprites
from visuals import PANEL,TEXT,GOLD,icon
from i18n import t as tr

class CombatHUD(tk.Frame):
    def __init__(self,parent,app):
        super().__init__(parent,bg=PANEL)
        self.app=app
        self.art=tk.Canvas(self,width=58,height=58,bg=PANEL,highlightthickness=0);self.art.pack(side='left',padx=5)
        self.art.bind('<Button-3>',self.context)
        self.swap=ttk.Button(self,command=lambda:app.act(app.game.switch));self.swap.pack(side='right',padx=6)
        middle=tk.Frame(self,bg=PANEL);middle.pack(fill='both',expand=True)
        self.title=tk.Label(middle,bg=PANEL,fg=GOLD,anchor='w');self.title.pack(fill='x')
        self.points=tk.Canvas(middle,height=25,bg=PANEL,highlightthickness=0);self.points.pack(fill='x')
        self.points.bind('<Configure>',lambda e:self.paint_points())

    def context(self,event):
        from item_actions import show
        show(self.app,self.app.game.weapon,event,self)

    def refresh(self):
        g=self.app.game
        if not g.battle:self.pack_forget();return
        if not self.winfo_manager():self.pack(before=self.app.canvas,fill='x',pady=(0,5))
        weapon=g.weapon;self.art.delete('all')
        if weapon:icon(self.art,weapon,3,3,52)
        self.title.config(text=tr('update030.weapon',name=weapon['name'],ap=weapon['ap']) if weapon else tr('update030.no_weapon'))
        other=g.equipped.get('weapon2' if g.active=='weapon1' else 'weapon1')
        if other:
            self.swap.config(text=tr('update030.swap',name=other['name']))
            if not self.swap.winfo_manager():self.swap.pack(side='right',padx=6)
        else:self.swap.pack_forget()
        self.paint_points()

    def paint_points(self):
        g=self.app.game;c=self.points;c.delete('all')
        if not g.battle:return
        total=max(g.battle.get('max_ap',g.max_ap),g.battle['ap']);left=g.battle['ap']
        width=max(60,c.winfo_width());columns=max(1,int((width-55)//15))
        c.config(height=max(25,((total+columns-1)//columns)*15+4))
        c.create_text(0,11,text=f'{left}/{total}',anchor='w',fill=TEXT,font=('Segoe UI',9))
        for n in range(total):
            x=53+n%columns*15;y=4+n//columns*15
            c.create_rectangle(x,y,x+10,y+10,fill='#69ce85' if n<left else '#59615e',outline='')
