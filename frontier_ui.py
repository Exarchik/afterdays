from i18n import t as tr
"""Live character sheet and cartographer service."""
import tkinter as tk
from tkinter import ttk
import progression as p
import adventure as a
from visuals import PANEL, TEXT, GOLD

def player_text(g):
    w=g.weapon;s=p.stats(w) if w else {};base=s.get('damage',0)+2*(g.level-1) if w else 0
    lines=[tr('frontier_ui.0001', v0=g.level, v1=g.money),tr('frontier_ui.0002', v0=g.hp, v1=g.max_hp),
           tr('frontier_ui.0003', v0=g.battle['ap'] if g.battle else g.max_ap, v1=g.max_ap),
           tr('frontier_ui.0004', v0=g.defense, v1=min(45, g.protection_stat('evasion'))),
           tr('frontier_ui.0005', v0=g.protection_stat('regen')),
           tr('frontier_ui.0006', v0=g.weight, v1=g.capacity),tr('frontier_ui.0007', v0=g.rad_turns),
           '', tr('frontier_ui.0008'),w['name'] if w else tr('frontier_ui.0009')]
    if w:
        lines += [tr('frontier_ui.0010', v0=max(1, base - 2), v1=base + 2),
                  tr('frontier_ui.0011', v0=a.DAMAGE_TYPES[a.damage_type(w)][0]),
                  tr('frontier_ui.0012', v0=min(65, 5 + s.get('crit', 0))),
                  tr('frontier_ui.0013', v0=s.get('accuracy', 0), v1=4 * g.rank('marksman')),
                  tr('frontier_ui.0014'),
                  tr('frontier_ui.0015', v0=s.get('range', 0), v1=s.get('attack', 0)),
                  tr('frontier_ui.0016', v0=w['ap'], v1=w.get('durability', 100)),
                  f'{p.AMMO[w.get("ammo_type","pistol")][0]}: {g.count("ammo",w.get("ammo_type","pistol"))}']
    lines+=['',tr('frontier_ui.0017'),tr('frontier_ui.0018', v0=g.pending_perks)]
    for key,rank in g.perks.items():
        name,desc=p.PERKS[key];lines += [tr('frontier_ui.0019', v0=name, v1=rank),desc]
    if not g.perks:lines+=[tr('frontier_ui.0020')]
    labels={'damage':tr('frontier_ui.0021'),'range':tr('frontier_ui.0022'),'accuracy':tr('frontier_ui.0023'),'crit':tr('frontier_ui.0024'),'attack':tr('frontier_ui.0025'),
            'defense':tr('frontier_ui.0026'),'evasion':tr('frontier_ui.0027'),'vitality':tr('frontier_ui.0028'),'capacity':tr('frontier_ui.0029'),'regen':tr('frontier_ui.0030')}
    lines+=['',tr('frontier_ui.0031')]
    for item in g.equipped.values():
        if not item:continue
        for module in item.get('modules',[]):
            lines += [item['name']+' → '+module['name'],', '.join(f'{labels.get(k,k)} {v:+g}' for k,v in module['stats'].items())]
    return '\n'.join(lines)

class PlayerPanel(tk.Frame):
    def __init__(self,parent,app):
        super().__init__(parent,bg=PANEL);self.app=app
        self.xp=tk.Label(self,bg=PANEL,fg=GOLD);self.xp.pack(pady=(12,4))
        self.bar=ttk.Progressbar(self);self.bar.pack(fill='x',padx=12,pady=4)
        body=tk.Frame(self,bg=PANEL);body.pack(fill='both',expand=True,padx=8,pady=8)
        scroll=ttk.Scrollbar(body);scroll.pack(side='right',fill='y')
        self.text=tk.Text(body,bg=PANEL,fg=TEXT,wrap='word',font=('Segoe UI',10),relief='flat',width=30,yscrollcommand=scroll.set)
        self.text.pack(fill='both',expand=True);scroll.config(command=self.text.yview)
    def refresh(self):
        g=self.app.game;low=p.xp_for_level(g.level);high=p.xp_for_level(g.level+1)
        self.xp.config(text=tr('frontier_ui.0032', v0=g.xp - low, v1=high - low, v2=high - g.xp))
        self.bar.config(maximum=high-low,value=g.xp-low)
        pos=self.text.yview()[0];self.text.config(state='normal');self.text.delete('1.0','end')
        self.text.insert('end',player_text(g));self.text.config(state='disabled');self.text.yview_moveto(pos)

def cartographer(app):
    g=app.game
    if not g.cartographer:return
    window=app.popup(tr('frontier_ui.0033'),'420x240');t=g.traveler;size=t['box'][2]
    tk.Label(window,text=tr('frontier_ui.0034', v0=size, v1=size, v2=t['price']),bg=PANEL,fg=TEXT,font=('Segoe UI',13),pady=24).pack()
    status=tk.Label(window,text=tr('frontier_ui.0035') if t['purchased'] else tr('frontier_ui.0036'),bg=PANEL,fg=GOLD);status.pack()
    def buy():
        if g.buy_map():status.config(text=tr('frontier_ui.0037'));button.config(state='disabled')
        else:status.config(text=g.messages[-1])
        app.refresh()
    button=ttk.Button(window,text=tr('frontier_ui.0038'),command=buy,state='disabled' if t['purchased'] else 'normal');button.pack(pady=16)


def draw_metro(canvas,g,t,ox,oy):
    stations=g.metro_unlocked
    def point(n):
        x,y=g.cities[n];return ox+(x+.5)*t,oy+(y+.5)*t
    for city in stations[1:]:
        canvas.create_line(*point(0),*point(city),fill='#58d9d1',width=3,dash=(7,4))
    for city in stations:
        x,y=point(city)
        canvas.create_oval(x-7,y-7,x+7,y+7,fill='#173b3a',outline='#58d9d1',width=2)
        canvas.create_text(x,y,text=tr('frontier_ui.0039'),fill='#9afbf2',font=('Segoe UI',8,'bold'))


def metro(app):
    g=app.game
    if g.battle or g.city not in g.metro_unlocked:return
    window=app.popup(tr('frontier_ui.0040'),'540x380')
    tk.Label(window,text=tr('frontier_ui.0041')+g.city_name(g.city),bg=PANEL,fg=GOLD,font=('Segoe UI',14,'bold')).pack(pady=18)
    tk.Label(window,text=tr('frontier_ui.0042'),bg=PANEL,fg=TEXT).pack(pady=8)
    destinations=[n for n in g.metro_unlocked if n!=g.city]
    status=tk.Label(window,text='' if destinations else tr('frontier_ui.0043'),bg=PANEL,fg=GOLD,wraplength=490)
    status.pack(pady=8)
    def travel(destination):
        if g.metro_travel(destination):
            app.dialog=None;window.destroy();app.refresh()
        else:status.config(text=g.messages[-1])
    for city in destinations:
        cost=g.metro_cost(city)
        if cost:
            ttk.Button(window,text=tr('frontier_ui.0044', v0=g.city_name(city), v1=cost[1]),command=lambda city=city:travel(city)).pack(fill='x',padx=24,pady=6)
