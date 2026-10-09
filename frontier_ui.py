from i18n import t as tr
"""Live character sheet and cartographer service."""
import tkinter as tk
from tkinter import ttk
import progression as p
import adventure as a
from visuals import PANEL, TEXT, GOLD

def player_text(g):
    w=g.weapon;effective=p.mr.effective_weapon(g,w);s=p.mr.weapon_stats(g,w)
    lines=[tr('frontier_ui.0001', v0=g.level, v1=g.money)+tr('scav.xp_remaining',level=g.level+1,xp=p.xp_for_level(g.level+1)-g.xp),tr('frontier_ui.0002', v0=g.hp, v1=g.max_hp),
           tr('frontier_ui.0003', v0=g.battle['ap'] if g.battle else g.max_ap, v1=g.max_ap),
           tr('frontier_ui.0004', v0=g.defense, v1=max(0,min(45, g.protection_stat('evasion')))),
           tr('frontier_ui.0005', v0=g.protection_stat('regen')),
           tr('frontier_ui.0006', v0=g.weight, v1=g.capacity),tr('survival040.sheet',rad=g.radiation_injury,hunger=g.hunger),
           '', tr('frontier_ui.0008'),w['name'] if w else tr('frontier_ui.0009')]
    lines.extend(g.buff_descriptions())
    if g.radiation_sickness:lines.append(tr('survival040.sickness_tip'))
    if g.starving:lines.append(tr('survival040.hunger_tip'))
    if w:
        from damage_preview import description as damage_description
        lines.append(damage_description(g,w))
        lines += [tr('frontier_ui.0010', v0=max(1,p.mr.shot_damage(effective,g.level,-2)), v1=p.mr.shot_damage(effective,g.level,2)),
                  tr('frontier_ui.0011', v0=a.DAMAGE_TYPES[a.damage_type(w)][0]),
                  tr('frontier_ui.0012', v0=min(65, 5 + s.get('crit', 0))+(15 if g.fire_mode()=='aimed' else 0)),
                  tr('frontier_ui.0013', v0=s.get('accuracy', 0), v1=4 * g.rank('marksman')),
                  tr('frontier_ui.0014'),
                  tr('frontier_ui.0015', v0=s.get('range', 0), v1=s.get('attack', 0)),
                  tr('frontier_ui.0016', v0=g.shot_ap(w), v1=p.mr.condition(w)),
                  f'{p.AMMO[w.get("ammo_type","pistol")][0]}: {g.count("ammo",w.get("ammo_type","pistol"))}']
    if w:
        for kind,amount in p.mr.shot_components(w,g.level,0,a.damage_type(w)).items():
            lines.append(tr('modules.damage_component',kind=a.DAMAGE_TYPES[kind][0],amount=amount))
        lines.append(tr('modules.ammo_chance',chance=p.mr.chance(s.get('ammo_save_percent',0))))
    lines.append(tr('modules.reflect_chance',chance=p.mr.chance(g.protection_stat('reflect_percent'))))
    lines+=['',tr('frontier_ui.0017'),tr('frontier_ui.0018', v0=g.pending_perks)]
    for key,rank in g.perks.items():
        name,desc=p.PERKS[key];lines += [tr('frontier_ui.0019', v0=name, v1=rank),desc]
    if not g.perks:lines+=[tr('frontier_ui.0020')]
    labels={'damage':tr('frontier_ui.0021'),'range':tr('frontier_ui.0022'),'accuracy':tr('frontier_ui.0023'),'crit':tr('frontier_ui.0024'),'attack':tr('frontier_ui.0025'),
            'defense':tr('frontier_ui.0026'),'evasion':tr('frontier_ui.0027'),'vitality':tr('frontier_ui.0028'),'capacity':tr('frontier_ui.0029'),'regen':tr('frontier_ui.0030')}
    labels.update({key:tr('modules.'+key) for key in p.mr.PERCENT_STATS|{'damage_electric','damage_piercing'}})
    lines+=['',tr('frontier_ui.0031')]
    for item in g.equipped.values():
        if not item:continue
        for module in item.get('modules',[]):
            lines += [item['name']+' → '+module['name'],', '.join(f'{labels.get(k,k)} {v:+g}' for k,v in module['stats'].items())]
    return '\n'.join(lines)

class PlayerPanel(tk.Frame):
    def __init__(self,parent,app):
        """Ініціалізує об’єкт, його початковий стан і потрібні залежності."""
        super().__init__(parent,bg=PANEL);self.app=app
        self.xp=tk.Label(self,bg=PANEL,fg=GOLD);self.xp.pack(pady=(12,4))
        self.bar=ttk.Progressbar(self);self.bar.pack(fill='x',padx=12,pady=4)
        body=tk.Frame(self,bg=PANEL);body.pack(fill='both',expand=True,padx=8,pady=8)
        scroll=ttk.Scrollbar(body);scroll.pack(side='right',fill='y')
        self.text=tk.Text(body,bg=PANEL,fg=TEXT,wrap='word',font=('Segoe UI',10),relief='flat',width=30,yscrollcommand=scroll.set)
        self.text.pack(fill='both',expand=True);scroll.config(command=self.text.yview)
    def refresh(self):
        """Оновлює віджети відповідно до поточного стану гри."""
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


def draw_metro(canvas,g,t,ox,oy,revealed=None):
    from metro_routes import draw
    draw(canvas,g,t,ox,oy,revealed)


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


def guide(app):
    g=app.game
    if not g.guide:return
    window=app.popup(tr('journey.guide'),'590x530')
    tk.Label(window,text=tr('journey.guide'),bg=PANEL,fg=GOLD,font=('Segoe UI',16,'bold')).pack(pady=14)
    tk.Label(window,text=tr('journey.guide_info'),bg=PANEL,fg=TEXT,wraplength=530,justify='left').pack(padx=20,pady=8)
    choices=g.guide_destinations()
    status=tk.Label(window,text='' if choices else tr('journey.none'),bg=PANEL,fg=GOLD);status.pack()
    def travel(city):
        if not app.route.start_guide(city):status.config(text=g.messages[-1]);app.refresh();return
        app.dialog=None;window.destroy();app.refresh()
    for choice in choices:
        ttk.Button(window,text=tr('journey.destination',city=g.city_name(choice['city']),steps=choice['steps'],price=choice['price']),command=lambda city=choice['city']:travel(city)).pack(fill='x',padx=24,pady=6)
